from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict
import torch
import torch.nn
from pybiscus.core.ensure_filesystem import ensure_file_dir_exists
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier
from pybiscus.flower.utils_server import get_params
from pybiscus.core.ensure_filesystem import ensure_file_dir_exists, ensure_dir_exists

# --------------------------------------------------------

class ConfigResultClientWatermarkingData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    save_as_cp: bool = True
    reporting_sub_dir: str = "rounds"
    client_watermaked_model_prefix: str = "client_watermarked_model"

    model_config = ConfigDict(extra="forbid")

class ConfigResultClientWatermarking(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "ClientWatermarking"
    name:   Literal["client watermarking"]

    config: ConfigResultClientWatermarkingData

    model_config = ConfigDict(extra="forbid")

# --------------------------------------------------------

def loss_watermark(weight: torch.tensor, secret_key:torch.tensor, fingerprint: torch.tensor):
    partially_reconstructed_fingerprint = weight.mean(0) @ secret_key
    criterion = lambda x, y: torch.sum(torch.relu(1 - (x * y)))
    return criterion(partially_reconstructed_fingerprint, fingerprint)

def extract_fingerprint(weight: torch.nn, secret_key: torch.tensor):
    with torch.no_grad():
        reconstructed_fingerprint = torch.where((weight.mean(0) @ secret_key) >= 0 , 1, -1 )
    return reconstructed_fingerprint

def watermark_detection_rate_fingerprint(
    reconstructed_fingerprint: torch.tensor, fingerprint : torch.tensor
) -> tuple[float, float]:
    with torch.no_grad():
        res=1-((reconstructed_fingerprint != fingerprint).sum()/fingerprint.size(0)).item()
    return res

def watermark_key_generation(nb_clients: int, size_layer: int, size_fingerprint: int):
    f1 = torch.randint(0,2,(size_fingerprint,), device="cuda") * 2 - 1
    f1 = f1.float()
    f2 = -f1.clone()

    f1.requires_grad = True
    f2.requires_grad = True

    sk1 = torch.randn((size_layer,size_fingerprint), device="cuda", requires_grad=True)
    sk2 = sk1.clone()

    print([f1,f2])
    return [f1,f2], [sk1,sk2]

def traitor_tracing(nb_clients: int, fingerprints = list[torch.tensor], secret_keys = list[torch.tensor]):
    max = -1
    max_i = -1
    for i in range(nb_clients):
        reconstructed_fingerprint = extract_fingerprint(0,secret_keys[i])
        WSR = watermark_detection_rate_fingerprint(reconstructed_fingerprint, fingerprints[i])
        if WSR > max:
            max = WSR
            max_i = i
    return max_i, max

# --------------------------------------------------------

class ResultClientWatermarking(ResultModifier):

    def __init__(self, save_as_cp, reporting_sub_dir, client_watermaked_model_prefix):

        self.save_as_cp = save_as_cp
        self.reporting_sub_dir = reporting_sub_dir
        self.client_watermaked_model_prefix = client_watermaked_model_prefix

        self.model = None
        self.fabric = None
        self.reporting_path = None

        self.client_index = 0
        self.client_hash = {}

        #TODO: make it configurable
        self.fingerprints, self.secret_keys = watermark_key_generation(2,120,16)
        self.max_epoch = 50

        logm.console.log(f"💧 ResultClientWatermarking allocated !")

    def import_context(self):

        if self.model is None:
            from pybiscus.core.pybiscuscontext import pybiscus_context
            self.fabric = pybiscus_context["fabric"]
            self.model = pybiscus_context["model"]
            self.reporting_path = pybiscus_context["reporting_path"]

    def modify(
        self,
        round: int,
        cid: str, 
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        self.import_context()

        logm.console.log( f"WM modify( round={round} cid={cid}) w_sizes = {[len(w) for w in weights]}" )

        if cid not in self.client_hash:
            self.client_hash[cid] = self.client_index
            logm.console.log( f"cid={cid} <=> {self.client_hash[cid]}" )
            self.client_index += 1

        # compute new models weights:

        current_client = self.client_hash[cid]

        print(f"Client : {current_client}")
        for i in range(2):
            wsr = watermark_detection_rate_fingerprint(
                extract_fingerprint(self.model.model[-3].weight,
                                    self.secret_keys[i]),
                self.fingerprints[i]
            )
            print(f"\t WSR Client {i} = {wsr}")

        optimizer = torch.optim.SGD(
            [self.model.model[-3].weight], lr=1e-1
        )

        for i in range(self.max_epoch):
            optimizer.zero_grad(set_to_none=True)

            loss = loss_watermark(
                self.model.model[-3].weight,
                self.secret_keys[current_client],
                self.fingerprints[current_client])

            loss.backward()

            optimizer.step()

            print(f"Loss : {loss.item()}")

        print(f"Client : {current_client}")
        for i in range(2):
            wsr = watermark_detection_rate_fingerprint(
                extract_fingerprint(self.model.model[-3].weight,
                                    self.secret_keys[i]),
                self.fingerprints[i]
            )
            print(f"\t WSR Client {i} = {wsr}")

        if self.save_as_cp:

            state = {"model": self.model}

            round_path = self.reporting_path / self.reporting_sub_dir
            ensure_dir_exists(round_path)
            checkpoint_client_path = round_path / f"round_{round}" / f"{self.client_watermaked_model_prefix}_{cid}.cp"
            ensure_file_dir_exists(checkpoint_client_path)
            
            self.fabric.save(checkpoint_client_path, state)
            logm.console.log(f"[fabric] save 💧 watermarked client {cid} model 💾📍🗄️to : {checkpoint_client_path}")

        # get model weights after model transform
        computed_weights = get_params(self.model)

        return computed_weights
