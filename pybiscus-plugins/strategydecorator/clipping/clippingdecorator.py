from enum import Enum
from typing import ClassVar, Literal

import numpy as np
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# Bounds the norm of each client's update before the aggregation, whatever the strategy behind:
# FedAvg keeps its accuracy and one client can no longer pull the model as far as it wants
# (docs/robust-aggregation.md). The update is measured against what the client was sent.


class ClippingMode(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    fixed = "fixed"      # C = clipping_norm
    median = "median"    # C = median_factor x the median update norm of the round


class ConfigClippingDecoratorData(BaseModel):
    """mode: fixed (clipping_norm) or median (median_factor x the round's median update norm:
    set by itself, without lag, and a minority of clients cannot move it)"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    mode: ClippingMode = ClippingMode.median
    median_factor: float = Field(default=1.5, gt=0)
    clipping_norm: float = Field(default=2.0, gt=0)

    model_config = ConfigDict(extra="forbid")


class ConfigClippingDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Update norm clipping"
    PYBISCUS_GROUP: ClassVar[str] = "Robustness"
    # the server-side DP decorators clip already
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = ("serverdpfixed", "serverdpadaptive")
    # what each client was sent is known only outside the decorator that personalizes it
    PYBISCUS_AFTER: ClassVar[tuple] = ("personalizeclientsfitin",)

    name:   Literal["clipping"]
    config: ConfigClippingDecoratorData

    model_config = ConfigDict(extra="forbid")


def update_norm(params, reference) -> float:
    # integer buffers (BatchNorm's num_batches_tracked) are counters, not weights
    return float(np.sqrt(sum(float(np.sum((w - w0).astype(np.float64) ** 2))
                             for w, w0 in zip(params, reference) if np.issubdtype(w.dtype, np.floating))))


def clipped_params(params, reference, scale: float) -> list:
    return [w0 + ((w - w0) * scale).astype(w.dtype) if np.issubdtype(w.dtype, np.floating) else w
            for w, w0 in zip(params, reference)]


class ClippingStrategyDecorator(StrategyDecorator):

    def __init__(self, base_strategy, config):
        super().__init__(base_strategy)
        self.config = config
        self.fabric = pcpc.pybiscus_context.get(pcpc.FABRIC)
        self.global_params = None
        self.sent = {}

    def configure_fit(self, server_round, parameters, client_manager):
        instructions = super().configure_fit(server_round, parameters, client_manager)
        self.global_params = parameters_to_ndarrays(parameters)
        # kept only when a client was sent something else than the global model (personalization):
        # a copy per client would multiply the memory by the number of clients
        self.sent = {proxy.cid: parameters_to_ndarrays(fit_ins.parameters)
                     for proxy, fit_ins in instructions if fit_ins.parameters is not parameters}
        return instructions

    def aggregate_fit(self, server_round, results, failures):
        if not results or self.global_params is None:
            return super().aggregate_fit(server_round, results, failures)

        entries = []
        for proxy, res in results:
            reference = self.sent.get(proxy.cid, self.global_params)
            params = parameters_to_ndarrays(res.parameters)
            entries.append((proxy, res, reference, params, update_norm(params, reference)))
        norms = np.array([entry[4] for entry in entries])
        median = float(np.median(norms))
        clipping_norm = (self.config.clipping_norm if self.config.mode == ClippingMode.fixed
                         else self.config.median_factor * median)

        ratios, clipped = {}, []
        for proxy, res, reference, params, norm in entries:
            cid = str(res.metrics.get("cid", proxy.cid))
            if norm > clipping_norm:
                res.parameters = ndarrays_to_parameters(clipped_params(params, reference, clipping_norm / norm))
                clipped.append(cid)
            # a client far above the median round after round is a suspect
            ratios[cid] = norm / median if median > 0 else 0.0

        metrics = {
            "clip_norm": clipping_norm,
            "clip_fraction": float(np.mean(norms > clipping_norm)),
            "clip_update_norm_median": median,
            "clip_update_norm_max": float(norms.max()),
        }
        logm.console.log(f"✂️ Round {server_round} clipping " + " ".join(f"{k}={v:.4g}" for k, v in metrics.items())
                         + (f" clipped clients: {', '.join(sorted(clipped))}" if clipped else ""))
        if self.fabric is not None:
            for key, value in metrics.items():
                self.fabric.log(key, value, step=server_round)
            for cid, ratio in ratios.items():
                self.fabric.log(f"clip_ratio_{cid}", ratio, step=server_round)

        return super().aggregate_fit(server_round, results, failures)
