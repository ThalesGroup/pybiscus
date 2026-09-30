import math
from typing import ClassVar, Literal, Optional

import flwr as fl
import numpy as np
from flwr.common import parameters_to_ndarrays
from flwr.common.differential_privacy import get_norm
from flwr.server.strategy import (
    DifferentialPrivacyServerSideAdaptiveClipping,
    DifferentialPrivacyServerSideFixedClipping,
)
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

SERVER_DP_NAMES = ("serverdpfixed", "serverdpadaptive")

# the noise is calibrated on a plain mean of the clipped updates (each client moves it by at most
# C / n): a median, a selection or a server optimizer transforms that mean, and the guarantee
# computed here no longer describes them
NOT_A_MEAN = (
    fl.server.strategy.FedAvgM,
    fl.server.strategy.FedMedian,
    fl.server.strategy.FedTrimmedAvg,
    fl.server.strategy.Krum,
    fl.server.strategy.Bulyan,
    fl.server.strategy.FedOpt,
    fl.server.strategy.QFedAvg,
)


def innermost_strategy(strategy):
    # pybiscus decorators keep base_strategy, Flower's wrappers keep strategy
    while True:
        inner = getattr(strategy, "base_strategy", None) or getattr(strategy, "strategy", None)
        if inner is None:
            return strategy
        strategy = inner


def rdp_epsilon(noise_multiplier: float, rounds: int, delta: float) -> float:
    """(epsilon, delta) of `rounds` Gaussian mechanisms with every client taking part in each,
    through Renyi DP (Mironov 2017): epsilon = min over alpha of rounds * alpha / (2 z^2)
    + log(1 / delta) / (alpha - 1), minimum reached in closed form."""
    if noise_multiplier <= 0:
        return math.inf
    a = rounds / (2 * noise_multiplier ** 2)
    return a + 2 * math.sqrt(a * math.log(1 / delta))


# ------------------------------- configurations ----------------------------------------

class ConfigServerDPCommon(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    # z: the noise's standard deviation is z * C / num_sampled_clients
    noise_multiplier:    float = Field(default=0.1, ge=0)
    # unset: min_fit_clients of the strategy (every client takes part in the demos)
    num_sampled_clients: Optional[int] = Field(default=None, ge=1)
    # epsilon is reported for this delta, when every client takes part in every round
    delta:               float = Field(default=1e-5, gt=0, lt=1)

    model_config = ConfigDict(extra="forbid")


class ConfigServerDPFixedData(ConfigServerDPCommon):
    """Central differential privacy with a fixed clipping norm, see
    flwr.server.strategy.DifferentialPrivacyServerSideFixedClipping. clipping_norm: bound C on the
    norm of each client's update (w_client - w_global); the clients' weight_drift under FedProx
    mu 0 shows its usual size."""
    clipping_norm: float = Field(default=1.0, gt=0)


class ConfigServerDPAdaptiveData(ConfigServerDPCommon):
    """Central differential privacy with a clipping norm adapted every round so that about
    target_clipped_quantile of the clients get clipped, see
    flwr.server.strategy.DifferentialPrivacyServerSideAdaptiveClipping. The count of clipped
    clients is noised too (clipped_count_stddev, num_sampled_clients / 20 if unset): Flower
    requires noise_multiplier < 2 * clipped_count_stddev."""
    initial_clipping_norm:   float = Field(default=0.1, gt=0)
    target_clipped_quantile: float = Field(default=0.5, ge=0, le=1)
    clip_norm_lr:            float = Field(default=0.2, gt=0)
    clipped_count_stddev:    Optional[float] = Field(default=None, ge=0)


# personalized models make the update measured against the global one include the
# personalization, and two DP decorators would noise twice
INCOMPATIBLE = ("personalizeclientsfitin",) + SERVER_DP_NAMES


class ConfigServerDPFixed(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ServerDPFixedClipping"
    PYBISCUS_GROUP: ClassVar[str] = "Privacy"
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = INCOMPATIBLE
    name:   Literal["serverdpfixed"]
    config: ConfigServerDPFixedData
    model_config = ConfigDict(extra="forbid")


class ConfigServerDPAdaptive(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ServerDPAdaptiveClipping"
    PYBISCUS_GROUP: ClassVar[str] = "Privacy"
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = INCOMPATIBLE
    name:   Literal["serverdpadaptive"]
    config: ConfigServerDPAdaptiveData
    model_config = ConfigDict(extra="forbid")


# ------------------------------- decorators --------------------------------------------

class ServerDPStrategyDecorator(StrategyDecorator):
    """Adapter: Flower's wrapper does the clipping and the noise, this class checks what would
    make it fail or mislead, and reports the clipping, the noise and epsilon every round."""

    def __init__(self, base_strategy, config):
        import pybiscus.core.pybiscuscontext as pcpc

        self.config = config
        self.fabric = pcpc.pybiscus_context.get(pcpc.FABRIC)
        check_float_state(pcpc.pybiscus_context.get(pcpc.MODEL))

        inner = innermost_strategy(base_strategy)
        if isinstance(inner, NOT_A_MEAN):
            logm.console.log(
                f"⚠️ server DP around {type(inner).__name__}: the noise is calibrated for a mean of "
                "the updates, the reported epsilon does not hold for this aggregation"
            )
        self.num_sampled_clients = config.num_sampled_clients or getattr(inner, "min_fit_clients", None)
        if self.num_sampled_clients is None:
            raise PybiscusValueException("server DP: set num_sampled_clients, the strategy has no min_fit_clients")
        # epsilon composes over the rounds only when every client takes part in each of them
        self.full_participation = getattr(inner, "fraction_fit", None) == 1
        self.weights_warned = False
        self.rounds_done = 0

        try:
            wrapper = self.make_wrapper(base_strategy, config)
        except ValueError as error:
            raise PybiscusValueException(f"server DP: {error}") from error
        super().__init__(wrapper)

    def make_wrapper(self, base_strategy, config):
        raise NotImplementedError

    def aggregate_fit(self, server_round, results, failures):
        wrapper = self.base_strategy
        clipping_norm = wrapper.clipping_norm
        if results and not failures:
            self.warn_unequal_weights(results)
            clipped = sum(self.update_norm(res) > clipping_norm for _, res in results) / len(results)
        else:
            clipped = None

        aggregated = super().aggregate_fit(server_round, results, failures)

        if aggregated[0] is not None:
            self.rounds_done += 1
            self.report(server_round, clipping_norm, clipped)
        return aggregated

    def update_norm(self, fit_res) -> float:
        params = parameters_to_ndarrays(fit_res.parameters)
        return get_norm([np.subtract(w, w0) for w, w0 in zip(params, self.base_strategy.current_round_params)])

    def warn_unequal_weights(self, results) -> None:
        if not self.weights_warned and len({res.num_examples for _, res in results}) > 1:
            self.weights_warned = True
            logm.console.log(
                "⚠️ server DP: the clients have different num_examples; a weighted mean lets the "
                "largest ones move it by more than C / n, the reported epsilon underestimates them"
            )

    def report(self, server_round, clipping_norm, clipped) -> None:
        wrapper = self.base_strategy
        stddev = wrapper.noise_multiplier * clipping_norm / self.num_sampled_clients
        metrics = {"dp_clipping_norm": clipping_norm, "dp_noise_stddev": stddev}
        if clipped is not None:
            metrics["dp_clipped_fraction"] = clipped
        if self.full_participation:
            metrics["dp_epsilon"] = rdp_epsilon(self.config.noise_multiplier, self.rounds_done, self.config.delta)
        logm.console.log(
            f"🔒 Round {server_round} server DP " + " ".join(f"{key}={value:.4g}" for key, value in metrics.items())
            + ("" if self.full_participation else " (epsilon not computed: clients sampled)")
        )
        if self.fabric is not None:
            for key, value in metrics.items():
                if math.isfinite(value):
                    self.fabric.log(key, value, step=server_round)


class ServerDPFixedStrategyDecorator(ServerDPStrategyDecorator):
    def make_wrapper(self, base_strategy, config):
        return DifferentialPrivacyServerSideFixedClipping(
            base_strategy,
            noise_multiplier=config.noise_multiplier,
            clipping_norm=config.clipping_norm,
            num_sampled_clients=self.num_sampled_clients,
        )


class ServerDPAdaptiveStrategyDecorator(ServerDPStrategyDecorator):
    def make_wrapper(self, base_strategy, config):
        return DifferentialPrivacyServerSideAdaptiveClipping(
            base_strategy,
            noise_multiplier=config.noise_multiplier,
            num_sampled_clients=self.num_sampled_clients,
            initial_clipping_norm=config.initial_clipping_norm,
            target_clipped_quantile=config.target_clipped_quantile,
            clip_norm_lr=config.clip_norm_lr,
            clipped_count_stddev=config.clipped_count_stddev,
        )


def check_float_state(model) -> None:
    # Flower scales the whole update in place: an integer array (BatchNorm's num_batches_tracked)
    # raises a numpy casting error at the first aggregation
    if model is None:
        return
    integers = [key for key, value in model.state_dict().items() if not value.is_floating_point()]
    if integers:
        raise PybiscusValueException(
            f"server DP: the model has non-float state entries, which Flower's clipping cannot scale: {', '.join(integers)}"
        )
