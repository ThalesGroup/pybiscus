import itertools
import math
from enum import Enum
from typing import ClassVar, Literal, Optional

import numpy as np
from flwr.common import FitRes, ndarrays_to_parameters, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.flower.utils_server import set_params
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# FLTrust (Cao et al., NDSS 2021): the server trains the global model on a small set of trusted
# examples (data section trusted) and weighs each client by the cosine similarity of its update to
# the server's, set to 0 when negative, after scaling it to the server update's norm. The weights go
# through num_examples, so that FedAvg's weighted average gives the paper's aggregate
# (docs/robust-aggregation.md).

# num_examples is an integer: the trust scores, in [0, 1], keep 6 digits
TRUST_SCALE = 1_000_000


class NormalizeTo(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    median = "median"    # to the median client update norm: the server's direction, the clients' step
    # the paper's: every update scaled to the server update's norm. Measured with 100 trusted
    # examples and 3 local epochs (cifar10_fltrust.yml), it cost 18 points without attacker: the
    # server's update, overfitting its few examples, is twice as long as the clients'
    server = "server"


class ServerSteps(str, Enum):
    # the paper's server and clients run the same number of local iterations: on a few trusted
    # examples, the same number of epochs is a few steps only, whose direction and norm say little
    clients = "clients"  # as many optimizer steps as the median client
    epochs = "epochs"    # local_epochs over the trusted examples


class ConfigFLTrustDecoratorData(BaseModel):
    """each client weighed by the cosine similarity of its update to the server's update on the
    trusted examples (0 when negative), its update scaled to normalize_to's norm; server_steps: the
    server trains as many optimizer steps as the median client (its number of examples x the local
    epochs / the trusted batch size), or local_epochs epochs over the trusted examples"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    server_steps: ServerSteps = Field(default=ServerSteps.clients, description=
        "clients: the server trains as many optimizer steps as the median client (as the paper's same number of local "
        "iterations; set the trusted batch size to the clients'); epochs: local_epochs over the trusted examples")

    normalize_to: NormalizeTo = Field(default=NormalizeTo.median, description=
        "median: every update scaled to the median client update norm; server: to the server update's norm (the "
        "paper's), whose few trusted examples may make a step much longer or shorter than the clients'")
    local_epochs: Optional[int] = Field(default=None, ge=1, description=
        "epochs over the trusted examples (server_steps: epochs), or the clients' epochs the steps are counted on; "
        "the clients' local epochs if unset")

    model_config = ConfigDict(extra="forbid")


class ConfigFLTrustDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FLTrust (trusted examples)"
    PYBISCUS_GROUP: ClassVar[str] = "Robustness"
    # it sets the norms itself; the DP decorators clip and add noise to what it weighs
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = ("clipping", "serverdpfixed", "serverdpadaptive", "personalizeclientsfitin")
    # its weights go through num_examples: a strategy ignoring them (median, Krum) would drop them
    PYBISCUS_STRATEGIES: ClassVar[tuple] = ("fedavg", "fedprox")
    PYBISCUS_DATA_SECTIONS: ClassVar[tuple] = ("trusted",)

    name:   Literal["fltrust"]
    config: ConfigFLTrustDecoratorData

    model_config = ConfigDict(extra="forbid")


def is_weight(array: np.ndarray) -> bool:
    # integer buffers (BatchNorm's num_batches_tracked) are counters, not weights
    return np.issubdtype(array.dtype, np.floating)


def flat_update(global_weights, weights) -> np.ndarray:
    return np.concatenate([(w.astype(np.float64) - w0).ravel() for w0, w in zip(global_weights, weights) if is_weight(w0)])


def trust_scores(server_update: np.ndarray, client_updates: list) -> list[float]:
    server_norm = np.linalg.norm(server_update)
    scores = []
    for update in client_updates:
        norm = np.linalg.norm(update)
        cosine = float(update @ server_update / (norm * server_norm)) if norm > 0 and server_norm > 0 else 0.0
        scores.append(max(cosine, 0.0))
    return scores


def rescaled(global_weights, weights, factor: float) -> list[np.ndarray]:
    return [(w0 + factor * (w.astype(np.float64) - w0)).astype(w0.dtype) if is_weight(w0) else w0
            for w0, w in zip(global_weights, weights)]


class FLTrustStrategyDecorator(StrategyDecorator):
    """FLTrust: clients weighed by the direction of their update against the server's on trusted examples."""

    def __init__(self, base_strategy, config):
        super().__init__(base_strategy)
        self.config = config
        self.fabric = pcpc.pybiscus_context.get(pcpc.FABRIC)
        self.model = pcpc.pybiscus_context.get(pcpc.MODEL)
        self.trusted = pcpc.pybiscus_context.get(pcpc.TRUSTED_SET)
        if self.trusted is None:
            raise PybiscusValueException("fltrust: the server's data has no trusted section (data.config.trusted)")
        server_run = (pcpc.pybiscus_context.get(pcpc.SERVER_CONFIG) or {}).get("server_run", {})
        self.local_epochs = config.local_epochs or server_run.get("clients_fit_local_epochs") or 1
        self.global_weights = None

    def configure_fit(self, server_round, parameters, client_manager):
        self.global_weights = parameters_to_ndarrays(parameters)
        return super().configure_fit(server_round, parameters, client_manager)

    def server_steps(self, results) -> int:
        if self.config.server_steps == ServerSteps.epochs:
            return self.local_epochs * len(self.trusted)
        examples = float(np.median([res.num_examples for _, res in results]))
        return self.local_epochs * math.ceil(examples / self.trusted.batch_size)

    def server_update(self, steps: int) -> np.ndarray:
        # imported here: the client module's import, while the server loads the plugins, came back
        # partially initialized (byzantine plugin)
        from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclient import parse_optimizers

        # the model is the one the strategy evaluates with: its state is put back after the training
        saved = {key: value.detach().clone() for key, value in self.model.state_dict().items()}
        try:
            set_params(self.model, self.global_weights)
            # a fresh optimizer every round, as the clients' optimizer_state reset; schedulers left
            # out: a few steps on the trusted examples are not an epoch of the task
            optimizers, _ = parse_optimizers(self.model.configure_optimizers())
            optimizer = self.fabric.setup_optimizers(optimizers[0])
            self.model.train()
            # the trusted examples gone through again and again until the steps are done
            batches = itertools.chain.from_iterable(itertools.repeat(self.trusted))
            for batch_idx, batch in enumerate(itertools.islice(batches, steps)):
                loss = self.model.training_step(batch, batch_idx)["loss"]
                optimizer.zero_grad()
                self.fabric.backward(loss)
                optimizer.step()
            trained = [value.detach().cpu().numpy() for value in self.model.state_dict().values()]
        finally:
            self.model.load_state_dict(saved)
        return flat_update(self.global_weights, trained)

    def aggregate_fit(self, server_round, results, failures):
        if not results or self.global_weights is None:
            return super().aggregate_fit(server_round, results, failures)

        steps = self.server_steps(results)
        server_update = self.server_update(steps)
        client_weights = [parameters_to_ndarrays(res.parameters) for _, res in results]
        client_updates = [flat_update(self.global_weights, weights) for weights in client_weights]
        scores = trust_scores(server_update, client_updates)
        norms = [float(np.linalg.norm(update)) for update in client_updates]
        target = float(np.linalg.norm(server_update)) if self.config.normalize_to == NormalizeTo.server else float(np.median(norms))

        trusted_results, line = [], []
        for (proxy, res), weights, score, norm in zip(results, client_weights, scores, norms):
            cid = res.metrics.get("cid", proxy.cid)
            line.append(f"{cid}:{score:.3f}")
            if self.fabric is not None:
                self.fabric.log(f"fltrust_score_{cid}", score, step=server_round)
            if score <= 0 or norm == 0:
                continue
            # a new FitRes: the decorators outside this one keep the update the client sent
            trusted_results.append((proxy, FitRes(status=res.status, parameters=ndarrays_to_parameters(rescaled(self.global_weights, weights, target / norm)),
                                                  num_examples=max(1, round(score * TRUST_SCALE)), metrics=res.metrics)))
        logm.console.log(f"🛡️ Round {server_round} FLTrust trust scores " + " ".join(line)
                         + f" (server: {steps} steps, update norm {np.linalg.norm(server_update):.3f}; median client norm {np.median(norms):.3f}; "
                         + f"{len(results) - len(trusted_results)} left out)")
        if self.fabric is not None:
            self.fabric.log("fltrust_server_norm", float(np.linalg.norm(server_update)), step=server_round)
            self.fabric.log("fltrust_left_out", len(results) - len(trusted_results), step=server_round)
        if not trusted_results:
            logm.console.log(f"🛡️ Round {server_round} FLTrust: no client update points the server's way, the global model is kept")
        return super().aggregate_fit(server_round, trusted_results, failures)
