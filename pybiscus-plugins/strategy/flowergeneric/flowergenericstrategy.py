from typing import ClassVar, Literal

import flwr as fl
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.flower.flowerstrategy import ConfigFlowerFailuresData, ConfigFlowerSamplingData, FlowerStrategyFactory

# Flower's other server-side strategies, used as they are (FedAvg itself is in the core).
# Each config lists exactly the scalar parameters its Flower class accepts: most FedAvg
# subclasses do not take `inplace`, FaultTolerantFedAvg does not take `accept_failures`,
# and Flower rejects unknown constructor arguments.


# ------------------------------- FedAvgM -------------------------------------

class ConfigFedAvgMData(ConfigFlowerFailuresData):
    """Server-side momentum, see flwr.server.strategy.FedAvgM."""
    server_learning_rate: float = Field(default=1.0, gt=0, description='server learning rate: the size of the step the server takes along the aggregated update')
    server_momentum:      float = Field(default=0.0, ge=0, lt=1, description="momentum of the server's steps; 0: plain FedAvg")


class ConfigFedAvgM(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedAvgM"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"
    name:   Literal["fedavgm"]
    config: ConfigFedAvgMData
    model_config = ConfigDict(extra="forbid")


class FedAvgMFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvgM


# ------------------------------- FedProx -------------------------------------
# the server only sends proximal_mu in the fit config; the proximal term itself is added by the
# client's train_loop. A client that ignores it would silently train as with FedAvg
# mu scales with the drift: measured on cifar10 (launch/campaign/cifar10_fedprox.yml, dirichlet
# 0.3, 3 local epochs), ||w - w_global|| after local training is about 1, so the term is about
# mu / 2 next to a data loss of 2. Up to 0.01 the accuracy stays within FedAvg's noise; 0.1 slows
# the learning and 1 almost stops it (DEVLOG)

class ConfigFedProxData(ConfigFlowerFailuresData):
    """FedAvg with a proximal term mu/2 * ||w - w_global||^2 in the clients' loss, which limits
    their drift from the global model, see flwr.server.strategy.FedProx. mu = 0 is FedAvg."""
    proximal_mu: float = Field(default=0.01, ge=0, description="weight of the proximal term mu/2 * ||w - w_global||^2 in the clients' loss, which limits their drift; 0: FedAvg")


class ConfigFedProx(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedProx"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"
    name:   Literal["fedprox"]
    config: ConfigFedProxData
    model_config = ConfigDict(extra="forbid")


class FedProxFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedProx


# ------------------------- FedAdam / FedYogi / FedAdagrad ---------------------
# server-side adaptive optimizers, applied to the pseudo-gradient (mean of the clients' weights
# minus the global ones). With a tiny tau, the first update is eta_norm * sign(delta): Flower's
# FedAdam / FedAdagrad eta 0.1 moved every weight by about 0.07 whatever the clients learned, far
# above a CNN's weights (0.05 to 0.1), and cifar10 stayed at chance (0.10). eta 1e-2 learns; a
# larger tau (1e-3, FedYogi's Flower default) crushed this model's small updates instead. Measured
# with launch/campaign (cifar10, 3 clients, 5 rounds): eta 1e-2 / tau 1e-9 matches FedAvg with
# dirichlet shares and exceeds it with iid ones, for the three strategies (DEVLOG).
# eta_l, the clients' learning rate, is stored by Flower but used by none of these strategies:
# each model sets its own.

class ConfigFedAdamData(ConfigFlowerFailuresData):
    """Server-side Adam, see flwr.server.strategy.FedAdam. eta: server learning rate; tau: adaptivity
    (a tiny tau makes every step the sign of the update); eta_l: informative only (unused by Flower)."""
    eta:    float = Field(default=1e-2, gt=0, description='server learning rate: the size of the step the server takes along the aggregated update')
    eta_l:  float = Field(default=0.1,  gt=0, description="the clients' learning rate, informative only: Flower does not use it")
    beta_1: float = Field(default=0.9,  ge=0, lt=1, description="decay of the first moment (momentum) of the server's Adam")
    beta_2: float = Field(default=0.99, ge=0, lt=1, description="decay of the second moment of the server's Adam")
    tau:    float = Field(default=1e-9, gt=0, description='adaptivity: added to the denominator; tiny, every step is about the sign of the update')


class ConfigFedAdam(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedAdam"
    PYBISCUS_GROUP: ClassVar[str] = "Server optimizers"
    name:   Literal["fedadam"]
    config: ConfigFedAdamData
    model_config = ConfigDict(extra="forbid")


class FedAdamFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAdam


class ConfigFedYogiData(ConfigFlowerFailuresData):
    """Server-side Yogi, see flwr.server.strategy.FedYogi. eta: server learning rate; tau:
    adaptivity; eta_l: informative only (unused by Flower)."""
    eta:    float = Field(default=0.01,   gt=0, description='server learning rate: the size of the step the server takes along the aggregated update')
    eta_l:  float = Field(default=0.0316, gt=0, description="the clients' learning rate, informative only: Flower does not use it")
    beta_1: float = Field(default=0.9,    ge=0, lt=1, description="decay of the first moment (momentum) of the server's Yogi")
    beta_2: float = Field(default=0.99,   ge=0, lt=1, description="decay of the second moment of the server's Yogi")
    tau:    float = Field(default=1e-9,   gt=0, description='adaptivity: added to the denominator; tiny, every step is about the sign of the update')


class ConfigFedYogi(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedYogi"
    PYBISCUS_GROUP: ClassVar[str] = "Server optimizers"
    name:   Literal["fedyogi"]
    config: ConfigFedYogiData
    model_config = ConfigDict(extra="forbid")


class FedYogiFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedYogi


class ConfigFedAdagradData(ConfigFlowerFailuresData):
    """Server-side Adagrad, see flwr.server.strategy.FedAdagrad. eta: server learning rate; tau:
    adaptivity (a tiny tau makes every step the sign of the update); eta_l: informative only."""
    eta:   float = Field(default=1e-2, gt=0, description='server learning rate: the size of the step the server takes along the aggregated update')
    eta_l: float = Field(default=0.1,  gt=0, description="the clients' learning rate, informative only: Flower does not use it")
    tau:   float = Field(default=1e-9, gt=0, description='adaptivity: added to the denominator; tiny, every step is about the sign of the update')


class ConfigFedAdagrad(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedAdagrad"
    PYBISCUS_GROUP: ClassVar[str] = "Server optimizers"
    name:   Literal["fedadagrad"]
    config: ConfigFedAdagradData
    model_config = ConfigDict(extra="forbid")


class FedAdagradFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAdagrad


# ------------------------- robust aggregation ---------------------------------

class ConfigFedMedianData(ConfigFlowerFailuresData):
    """Coordinate-wise median, see flwr.server.strategy.FedMedian."""
    inplace: bool = Field(default=True, description='aggregate in place, saving memory; same result')


class ConfigFedMedian(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedMedian"
    PYBISCUS_GROUP: ClassVar[str] = "Robust aggregation"
    name:   Literal["fedmedian"]
    config: ConfigFedMedianData
    model_config = ConfigDict(extra="forbid")


class FedMedianFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedMedian


class ConfigFedTrimmedAvgData(ConfigFlowerFailuresData):
    """Trimmed mean, `beta` = fraction cut at each end, see flwr.server.strategy.FedTrimmedAvg."""
    beta: float = Field(default=0.2, ge=0, lt=0.5, description='fraction of the values cut at each end of every coordinate before averaging')


class ConfigFedTrimmedAvg(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedTrimmedAvg"
    PYBISCUS_GROUP: ClassVar[str] = "Robust aggregation"
    name:   Literal["fedtrimmedavg"]
    config: ConfigFedTrimmedAvgData
    model_config = ConfigDict(extra="forbid")


class FedTrimmedAvgFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedTrimmedAvg


class ConfigKrumData(ConfigFlowerFailuresData):
    """Byzantine-robust selection, needs more than 2 * num_malicious_clients + 2 clients,
    see flwr.server.strategy.Krum (num_clients_to_keep = 0: Krum, > 0: Multi-Krum)."""
    num_malicious_clients: int = Field(default=0, ge=0, description='attackers to tolerate, f: needs more than 2f + 2 clients')
    num_clients_to_keep:   int = Field(default=0, ge=0, description='0: Krum keeps the single most central update; > 0: Multi-Krum averages this many')


class ConfigKrum(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "Krum"
    PYBISCUS_GROUP: ClassVar[str] = "Robust aggregation"
    name:   Literal["krum"]
    config: ConfigKrumData
    model_config = ConfigDict(extra="forbid")


class KrumFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.Krum


class ConfigBulyanData(ConfigFlowerFailuresData):
    """Krum pre-selection + trimmed mean, needs at least 4 * num_malicious_clients + 3 clients,
    see flwr.server.strategy.Bulyan."""
    num_malicious_clients: int = Field(default=0, ge=0, description='attackers to tolerate, f: needs at least 4f + 3 clients')
    krum_to_keep:          int = Field(default=0, ge=0, description='updates the Krum pre-selection keeps before the trimmed mean')

    # Flower raises a ValueError in the middle of the aggregation below 4f + 3 clients: the server
    # crashed at the first round, or as soon as a client was missing
    @model_validator(mode="after")
    def _enough_clients(self):
        needed = 4 * self.num_malicious_clients + 3
        if self.min_fit_clients < needed:
            raise ValueError(f"bulyan: min_fit_clients must be at least 4 * num_malicious_clients + 3 = {needed} (got {self.min_fit_clients})")
        return self


class ConfigBulyan(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "Bulyan"
    PYBISCUS_GROUP: ClassVar[str] = "Robust aggregation"
    name:   Literal["bulyan"]
    config: ConfigBulyanData
    model_config = ConfigDict(extra="forbid")


class BulyanFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.Bulyan

    def strategy_kwargs(self) -> dict:
        # the pre-selection rule stays Flower's default (Krum); its own parameter `to_keep` goes
        # through Bulyan's **aggregation_rule_kwargs, renamed here to say whose parameter it is
        kwargs = self.config.model_dump()
        kwargs["to_keep"] = kwargs.pop("krum_to_keep")
        return kwargs


# ------------------------- fairness / fault tolerance -------------------------

class ConfigQFedAvgData(ConfigFlowerFailuresData):
    """q-Fair FedAvg, see flwr.server.strategy.QFedAvg. qffl_learning_rate: QFedAvg rebuilds each
    client's gradient as (w - w_client) / qffl_learning_rate, which assumes plain SGD steps at that
    rate; with momentum and many local steps, the clients' own rate (0.001 for cifar10) learned
    worst: 0.1 did best (launch/campaign, DEVLOG). Note: Flower weighs every client with the same
    loss, the global model's one evaluated by the server, so q does not favour the clients the
    global model serves badly."""
    q_param:            float = Field(default=0.2, ge=0, description='fairness: the larger, the more weight to the clients with a high loss; 0: FedAvg-like')
    qffl_learning_rate: float = Field(default=0.1, gt=0, description="rate used to rebuild each client's gradient from its update (0.1 did best on cifar10)")


class ConfigQFedAvg(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "QFedAvg"
    PYBISCUS_GROUP: ClassVar[str] = "Fairness & fault tolerance"
    name:   Literal["qfedavg"]
    config: ConfigQFedAvgData
    model_config = ConfigDict(extra="forbid")


class QFedAvgFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.QFedAvg


class ConfigFaultTolerantFedAvgData(ConfigFlowerSamplingData):
    """FedAvg tolerating failed clients, see flwr.server.strategy.FaultTolerantFedAvg."""
    min_completion_rate_fit:      float = Field(default=0.5, ge=0, le=1, description='fewest fraction of the sampled clients whose training must succeed')
    min_completion_rate_evaluate: float = Field(default=0.5, ge=0, le=1, description='fewest fraction of the sampled clients whose evaluation must succeed')


class ConfigFaultTolerantFedAvg(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FaultTolerantFedAvg"
    PYBISCUS_GROUP: ClassVar[str] = "Fairness & fault tolerance"
    name:   Literal["faulttolerantfedavg"]
    config: ConfigFaultTolerantFedAvgData
    model_config = ConfigDict(extra="forbid")


class FaultTolerantFedAvgFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FaultTolerantFedAvg


# name -> (factory, config) exported by the plugin
FLOWER_STRATEGIES = {
    "fedavgm":             (FedAvgMFactory,             ConfigFedAvgM),
    "fedprox":             (FedProxFactory,             ConfigFedProx),
    "fedadam":             (FedAdamFactory,             ConfigFedAdam),
    "fedyogi":             (FedYogiFactory,             ConfigFedYogi),
    "fedadagrad":          (FedAdagradFactory,          ConfigFedAdagrad),
    "fedmedian":           (FedMedianFactory,           ConfigFedMedian),
    "fedtrimmedavg":       (FedTrimmedAvgFactory,       ConfigFedTrimmedAvg),
    "krum":                (KrumFactory,                ConfigKrum),
    "bulyan":              (BulyanFactory,              ConfigBulyan),
    "qfedavg":             (QFedAvgFactory,             ConfigQFedAvg),
    "faulttolerantfedavg": (FaultTolerantFedAvgFactory, ConfigFaultTolerantFedAvg),
}
