from typing import ClassVar, Literal

import numpy as np
from flwr.common import FitRes, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# FoolsGold (Fung et al., arXiv:1808.04866, Algorithm 1): clients whose updates keep pointing the same
# way, round after round, are taken for sybils and weighed down. The history of each client is the
# sum of its updates; the weights go through num_examples, so that FedAvg's weighted average applies
# them (the paper adds the weighted updates of a federated SGD). Not the paper's feature importance
# (output layer weights): every weight counts (docs/robust-aggregation.md).

# num_examples is an integer: the weights, in [0, 1], keep 6 digits
WEIGHT_SCALE = 1_000_000


class ConfigFoolsGoldDecoratorData(BaseModel):
    """each client weighed by how unlike any other client its history of updates (the sum of its
    updates so far) is: 1 - its largest cosine similarity to another client's history, pardoned
    when the other one looks even more like a sybil, rescaled to a maximum of 1 and passed through
    a logit of confidence kappa"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    kappa: float = Field(default=1.0, gt=0, description="confidence of the logit: larger, the weights go faster to 0 or 1 (the paper's 1)")

    model_config = ConfigDict(extra="forbid")


class ConfigFoolsGoldDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FoolsGold (alike clients)"
    PYBISCUS_GROUP: ClassVar[str] = "Robustness"
    # fltrust sets the weights too; the DP decorators add noise to what it compares; the updates
    # are measured against the global model, not what each client was sent
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = ("fltrust", "serverdpfixed", "serverdpadaptive", "personalizeclientsfitin")
    # it compares what the clients sent: outside the clipping, which may then reject or clip them
    PYBISCUS_AFTER: ClassVar[tuple] = ("clipping",)
    # its weights go through num_examples: a strategy ignoring them (median, Krum) would drop them
    PYBISCUS_STRATEGIES: ClassVar[tuple] = ("fedavg", "fedprox")

    name:   Literal["foolsgold"]
    config: ConfigFoolsGoldDecoratorData

    model_config = ConfigDict(extra="forbid")


def flat_update(global_weights, weights) -> np.ndarray:
    # integer buffers (BatchNorm's num_batches_tracked) are counters, not weights
    return np.concatenate([(w.astype(np.float64) - w0).ravel() for w0, w in zip(global_weights, weights)
                           if np.issubdtype(w0.dtype, np.floating)])


def foolsgold_weights(histories: list, kappa: float) -> np.ndarray:
    n = len(histories)
    stacked = np.stack(histories)
    norms = np.linalg.norm(stacked, axis=1)
    norms[norms == 0] = 1.0
    unit = stacked / norms[:, None]
    cs = unit @ unit.T
    np.fill_diagonal(cs, -np.inf)
    v = cs.max(axis=1)
    np.fill_diagonal(cs, 0.0)
    # pardoning: an honest client resembling a sybil is not punished as much as the sybil
    for i in range(n):
        for j in range(n):
            if i != j and v[j] > v[i]:
                cs[i, j] *= v[i] / v[j]
    np.fill_diagonal(cs, -np.inf)
    alpha = np.clip(1.0 - cs.max(axis=1), 0.0, 1.0)
    if alpha.max() == 0:
        return alpha
    alpha = alpha / alpha.max()
    with np.errstate(divide="ignore"):
        # alpha 1 gives +inf and 0 gives -inf: clipped to 1 and 0, as the paper says
        logit = kappa * (np.log(alpha / (1.0 - alpha)) + 0.5)
    return np.clip(np.nan_to_num(logit, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)


class FoolsGoldStrategyDecorator(StrategyDecorator):
    """FoolsGold: clients weighed down when their history of updates looks like another client's."""

    def __init__(self, base_strategy, config):
        super().__init__(base_strategy)
        self.config = config
        self.fabric = pcpc.pybiscus_context.get(pcpc.FABRIC)
        self.global_weights = None
        self.histories = {}

    def configure_fit(self, server_round, parameters, client_manager):
        self.global_weights = parameters_to_ndarrays(parameters)
        return super().configure_fit(server_round, parameters, client_manager)

    def aggregate_fit(self, server_round, results, failures):
        if len(results) < 2 or self.global_weights is None:
            return super().aggregate_fit(server_round, results, failures)

        cids = [str(res.metrics.get("cid", proxy.cid)) for proxy, res in results]
        for cid, (_, res) in zip(cids, results):
            update = flat_update(self.global_weights, parameters_to_ndarrays(res.parameters))
            self.histories[cid] = self.histories[cid] + update if cid in self.histories else update
        weights = foolsgold_weights([self.histories[cid] for cid in cids], self.config.kappa)
        if weights.max() == 0:
            # every history alike: the paper assumes one honest client at least, there is none to keep
            logm.console.log(f"🪙 Round {server_round} FoolsGold: every client looks like another, weights left as they were")
            return super().aggregate_fit(server_round, results, failures)

        weighted, line = [], []
        for cid, (proxy, res), weight in zip(cids, results, weights):
            line.append(f"{cid}:{weight:.3f}")
            if self.fabric is not None:
                self.fabric.log(f"foolsgold_weight_{cid}", float(weight), step=server_round)
            if weight <= 0:
                continue
            # a new FitRes: the decorators outside this one keep what the client sent
            weighted.append((proxy, FitRes(status=res.status, parameters=res.parameters,
                                           num_examples=max(1, round(float(weight) * WEIGHT_SCALE)), metrics=res.metrics)))
        logm.console.log(f"🪙 Round {server_round} FoolsGold weights " + " ".join(line) + f" ({len(results) - len(weighted)} left out)")
        if self.fabric is not None:
            self.fabric.log("foolsgold_left_out", len(results) - len(weighted), step=server_round)
        return super().aggregate_fit(server_round, weighted, failures)
