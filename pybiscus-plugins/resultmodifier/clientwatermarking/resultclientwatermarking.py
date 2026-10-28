from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
import torch
import torch.nn
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier
from pybiscus.flower.utils_server import get_params, set_params
from pybiscus.core.ensure_filesystem import ensure_file_dir_exists
from pybiscus.core.reportingoutputs import TAG, TaggedReportingOutputs, output_dir, output_file

# --------------------------------------------------------

class ConfigResultClientWatermarkingData(TaggedReportingOutputs):
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    nb_clients: int = Field(default=5, description='clients to give a fingerprint')
    key_size_layer: int = Field(default=2112, description='weights of the layer that carries the watermark')
    key_size_fingerprint: int = Field(default=256, description="bits of each client's fingerprint")

    save_as_cp: bool = Field(default=True, description='save each watermarked model as a checkpoint')
    reporting_sub_dir: str = Field(default="rounds", description='subdirectory of the reporting directory, one round_<n> directory per round inside')
    client_watermaked_model_prefix: str = Field(default="client_watermarked_model", description="prefix of the watermarked models' files")

    client_watermaking_traces_path: str = Field(default="client_watermarking_traces.txt", description='file of the watermarking traces (WSR of every client)')
    client_fingerprints_path: str = Field(default="client_fingerprints.csv", description="file matching each Flower client (cid) with its fingerprint, to find which client a leaked model came from")

    model_config = ConfigDict(extra="forbid")

    def reporting_outputs(self):
        return {"traces": output_file(TAG, self.client_watermaking_traces_path),
                "fingerprints": output_file(TAG, self.client_fingerprints_path),
                "checkpoints": output_dir(TAG, "watermarked_checkpoints")}

class ConfigResultClientWatermarking(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "ClientWatermarking"
    name:   Literal["client watermarking"]

    config: ConfigResultClientWatermarkingData

    model_config = ConfigDict(extra="forbid")

# --------------------------------------------------------
class TracerAndLogger:
    def __init__(self, path: str):
        self.path = path

    def __enter__(self):
        self.file = open(self.path, "a", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.file.close()

    def log(self, msg: str):
        self.file.write(msg + "\n")
        self.file.flush()
        # log using multiple logger (sent to manager according to configuration)
        logm.console.log(msg)

    def ilog(self, msg: str):
        self.file.write(msg + "\n")
        self.file.flush()
        # log using only interactive logger (not sent to manager)
        logm.interactiveConsole.log(msg)

# --------------------------------------------------------

def loss_watermark(weight: torch.tensor, secret_key:torch.tensor, fingerprint: torch.tensor):
    partially_reconstructed_fingerprint = secret_key @ weight.flatten()
    criterion = lambda x, y: torch.sum(torch.relu(1 - (x * y)))
    return criterion(partially_reconstructed_fingerprint, fingerprint)

def extract_fingerprint(weight: torch.nn, secret_key: torch.tensor):
    with torch.no_grad():
        reconstructed_fingerprint = torch.where((secret_key @ weight.flatten()) >= 0 , 1, -1 )
    return reconstructed_fingerprint

def watermark_detection_rate_fingerprint(
    reconstructed_fingerprint: torch.tensor, fingerprint : torch.tensor
) -> tuple[float, float]:
    with torch.no_grad():
        res=1-((reconstructed_fingerprint != fingerprint).sum()/fingerprint.size(0)).item()
    return res

def watermark_key_generation(nb_clients: int, size_layer: int, size_fingerprint: int):

    import pybiscus.core.pybiscuscontext as pcpc
    device = pcpc.pybiscus_context["model"].device

    n = size_fingerprint
    A = torch.randn(n, n, device=device)
    Q, R = torch.linalg.qr(A)
    fingerprints = [torch.where(Q[:, i] >= 0, 1, -1) for i in range(Q.shape[1])]

    # the key is fixed: only the layer is optimized
    sk = torch.randn((size_fingerprint,size_layer), device=device)

    return fingerprints, sk

def traitor_tracing(weight: torch.Tensor, secret_key: torch.Tensor, fingerprints: list[torch.Tensor]) -> tuple[int, float]:
    """the index of the fingerprint best read in this layer of a leaked model, and its WSR (match it
    with a client through the client_fingerprints file)"""
    reconstructed_fingerprint = extract_fingerprint(weight, secret_key)
    rates = [watermark_detection_rate_fingerprint(reconstructed_fingerprint, f) for f in fingerprints]
    best = max(range(len(rates)), key=rates.__getitem__)
    return best, rates[best]

# --------------------------------------------------------

class ResultClientWatermarking(ResultModifier):
    """Embeds a fingerprint of each client in the global weights it is sent (the model's `fc` layer
    carries the watermark), and traces how well each fingerprint can be read back. The match between
    Flower clients and fingerprints is written to `client_fingerprints_path`, the secret key and
    each fingerprint to the checkpoints, so that `traitor_tracing` finds which client a leaked model
    came from. A Flower client that reconnects gets a new cid, hence a new fingerprint."""

    # instantiated with its config's fields as keywords (personalizeclientsfitin): the config is
    # rebuilt, its outputs giving the paths
    def __init__(self, **config):

        self.conf = ConfigResultClientWatermarkingData(**config)
        self.save_as_cp = self.conf.save_as_cp
        nb_clients, key_size_layer, key_size_fingerprint = self.conf.nb_clients, self.conf.key_size_layer, self.conf.key_size_fingerprint

        self.model = None
        self.fabric = None

        self.client_index = 0
        self.client_hash = {}

        self.total_clients = nb_clients

        self.print_before = False

        #TODO: make it configurable
        self.fingerprints, self.secret_keys = watermark_key_generation(self.total_clients, key_size_layer, key_size_fingerprint)
        self.max_epoch = 50

    def import_context(self):

        from pybiscus.core.pybiscuscontext import pybiscus_context

        if self.model is None:
            self.fabric = pybiscus_context["fabric"]
            self.model = pybiscus_context["model"]

        self.clients_weights = pybiscus_context.get("clients_weights", {} )
        logm.console.log(f"context has {len(self.clients_weights)} clients_weights")

    def register_client(self, round: int, cid: str):
        """gives the next fingerprint to a client seen for the first time, and records the match on
        disk: the logs alone did not tell which client a leaked model came from"""

        index = self.client_index
        if index >= self.total_clients:
            logm.console.log(f"⚠️ watermarking: client {cid} beyond the {self.total_clients} clients configured (nb_clients), "
                             f"fingerprint {index} given; a client reconnecting gets a new cid")
        self.client_hash[cid] = index
        self.client_index += 1

        checkpoints = self.conf.output_path("checkpoints")
        if index == 0:
            ensure_file_dir_exists(checkpoints / "secret_key.pth")
            self.fabric.save(checkpoints / "secret_key.pth", {"secret_key": self.secret_keys})
            logm.console.log(f"[fabric] save 💧 Secret Key 💾📍🗄️to : {checkpoints / 'secret_key.pth'}")

        fingerprint_path = checkpoints / f"fingerprint_{cid}.pth"
        ensure_file_dir_exists(fingerprint_path)
        self.fabric.save(fingerprint_path, {"fingerprint": self.fingerprints[index], "index": index, "cid": cid})
        logm.console.log(f"[fabric] save 💧 Fingerprint {index} of client {cid} 💾📍🗄️to : {fingerprint_path}")

        matches = self.conf.output_path("fingerprints")
        new_file = not matches.exists()
        with open(matches, "a", encoding="utf-8") as f:
            if new_file:
                f.write("cid,fingerprint,first_round\n")
            f.write(f"{cid},{index},{round}\n")

    def modify(
        self,
        round: int,
        cid: str,
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        # csv possible presentation
        """
round,client,cid,wsr_before,wsr_after
1,0,5f5f3b3633fd4b6f85c2f49d5bf6586b,"{0: 0.6875, 1: 0.3125}","{0: 1.0, 1: 0.0}"
1,1,8043ab8c84404be8b8eb89ee9c41d2b8,"{0: 0.6875, 1: 0.3125}","{0: 0.0, 1: 1.0}"
2,0,5f5f3b3633fd4b6f85c2f49d5bf6586b,"{0: 0.6875, 1: 0.3125}","{0: 1.0, 1: 0.0}"
2,1,8043ab8c84404be8b8eb89ee9c41d2b8,"{0: 0.6875, 1: 0.3125}","{0: 0.0, 1: 1.0}"
        """

        self.import_context()

        for client_id, client_weights in self.clients_weights.items():
            logm.console.log( f"WM: I can access weights of client {client_id} !!! ")

        logm.interactiveConsole.log( f"WM modify( round={round} cid={cid}) w_sizes = {[len(w) for w in weights]}" )

        # the weights sent this round, not the server's model as it stands: that one holds the global
        # weights only when the server evaluated them
        set_params(self.model, weights)

        if cid not in self.client_hash:
            self.register_client(round, cid)

        watermarking_traces_path = self.conf.output_path("traces")

        with TracerAndLogger(watermarking_traces_path) as logger:
            current_client = self.client_hash[cid]
            #logger.log( f"\n*** Round {round} Client : {current_client} cid : {cid} ***\n")

            if self.print_before:

                logger.log(f"# Before Watermarking")
                for i in range(self.total_clients):
                    wsr = watermark_detection_rate_fingerprint(
                        extract_fingerprint(self.model.model.fc.weight,
                                            self.secret_keys),
                        self.fingerprints[i]
                    )
                    logger.log(f"\t WSR Client {i} = {wsr}")

            optimizer = torch.optim.SGD(
                [self.model.model.fc.weight], lr=1e-1
            )

            for i in range(self.max_epoch):
                optimizer.zero_grad(set_to_none=True)

                loss = loss_watermark(
                    self.model.model.fc.weight,
                    self.secret_keys,
                    self.fingerprints[current_client])

                loss.backward()

                optimizer.step()

                with torch.no_grad():
                    wsr = watermark_detection_rate_fingerprint(
                        extract_fingerprint(self.model.model.fc.weight,
                                            self.secret_keys),
                        self.fingerprints[current_client]
                    )

                    if wsr >= 0.98:
                        break

            #logger.log(f"# After Watermarking")
            for i in range(self.total_clients):
                wsr = watermark_detection_rate_fingerprint(
                    extract_fingerprint(self.model.model.fc.weight,
                                        self.secret_keys),
                    self.fingerprints[i]
                )
                logger.log(f"{round}\t{current_client}\t{i}\t{wsr}")

        if self.save_as_cp:

            checkpoint_client_path = self.conf.output_path("checkpoints") / f"round_{round}/client_{cid}.cp"

            state = {"model": self.model}

            ensure_file_dir_exists(checkpoint_client_path)
            self.fabric.save(checkpoint_client_path, state)
            logm.console.log(f"[fabric] save 💧 watermarked client {cid} checkpoint 💾📍🗄️to : {checkpoint_client_path}")

        logm.console.log(f"using module 💧 ResultClientWatermarking")

        # get model weights after model transform
        computed_weights = get_params(self.model)

        # return a copy of weights
        return computed_weights