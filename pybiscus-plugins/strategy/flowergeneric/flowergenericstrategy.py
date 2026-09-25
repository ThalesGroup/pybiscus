from collections import defaultdict
from functools import partial
from typing import ClassVar, Literal, Optional, Union

import flwr as fl
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory
from pybiscus.flower.utils_server import (
    evaluate_config,
    get_evaluate_fn,
    make_fit_config,
    weighted_average,
)


class FabricLoggingMixin:
    """Adds Pybiscus logging to a Flower strategy without replacing its aggregation."""

    # set by the factory after construction: Flower strategies reject unknown constructor arguments
    fabric = None

    def evaluate(self, server_round: int, parameters: Parameters) -> Optional[tuple[float, dict[str, Scalar]]]:
        eval_res = super().evaluate(server_round, parameters)
        if eval_res is None:
            return None

        _, metrics = eval_res
        emo = defaultdict(str, loss="📉", accuracy="🎯")
        logmsg = ""
        for key, value in metrics.items():
            logmsg += f"{emo[key]} {key}={value:.3f} "
            self.fabric.log(f"val_{key}_glob", value, step=server_round)
        logm.console.log(f"🔁 Round {server_round} 🧪 Test {logmsg}")

        return eval_res

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
    ) -> tuple[Optional[Parameters], dict[str, Scalar]]:
        # the Flower class aggregates: logging after super() keeps each strategy's own rule,
        # overriding the aggregation here would turn every strategy into a FedAvg
        aggregated = super().aggregate_fit(server_round, results, failures)

        if results:
            logm.console.log(
                f"🔁 Round:{server_round} aggregates using {type(self).__name__}\n"
                + "\n".join(f"🆔{client.cid} ⚖️{fit_res.num_examples}" for client, fit_res in results)
            )
            self._log_client_metrics("fit", server_round, results)

        return aggregated

    def aggregate_evaluate(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[Union[tuple[ClientProxy, EvaluateRes], BaseException]],
    ) -> tuple[Optional[float], dict[str, Scalar]]:
        aggregated = super().aggregate_evaluate(server_round, results, failures)
        self._log_client_metrics("val", server_round, results)
        return aggregated

    def _log_client_metrics(self, prefix, server_round, results) -> None:
        for client, res in results:
            cid = res.metrics.get("cid", client.cid)
            for key, value in res.metrics.items():
                self.fabric.log(f"{prefix}_{key}_{cid}", value, step=server_round)


def with_fabric_logging(flower_strategy_class):
    return type(f"Fabric{flower_strategy_class.__name__}", (FabricLoggingMixin, flower_strategy_class), {})


class FlowerStrategyFactory(FabricStrategyFactory):

    flower_strategy_class = None

    def __init__(self, model, fabric, testset, initial_parameters, config):
        self.model = model
        self.fabric = fabric
        self.testset = testset
        self.initial_parameters = initial_parameters
        self.config = config

    def strategy_kwargs(self) -> dict:
        return self.config.model_dump()

    def get_strategy(self, clients_fit_local_epochs):
        strategy = with_fabric_logging(self.flower_strategy_class)(
            evaluate_fn=get_evaluate_fn(testset=self.testset, model=self.model, fabric=self.fabric),
            on_fit_config_fn=make_fit_config(clients_fit_local_epochs),
            on_evaluate_config_fn=evaluate_config,
            fit_metrics_aggregation_fn=partial(weighted_average, context="fit"),
            evaluate_metrics_aggregation_fn=partial(weighted_average, context="evaluate"),
            initial_parameters=self.initial_parameters,
            **self.strategy_kwargs(),
        )
        strategy.fabric = self.fabric
        return strategy


# --------------------------- configurations ----------------------------------
# Each config lists exactly the scalar parameters its Flower class accepts: most FedAvg
# subclasses do not take `inplace`, FaultTolerantFedAvg does not take `accept_failures`,
# and Flower rejects unknown constructor arguments.

class ConfigFlowerSamplingData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    fraction_fit:          float = Field(default=1, ge=0, le=1)
    fraction_evaluate:     float = Field(default=1, ge=0, le=1)
    min_fit_clients:       int   = Field(default=2, ge=1)
    min_evaluate_clients:  int   = Field(default=2, ge=0)
    min_available_clients: int   = Field(default=2, ge=1)

    model_config = ConfigDict(extra="forbid")


class ConfigFlowerFailuresData(ConfigFlowerSamplingData):
    accept_failures: bool = True


# ------------------------------- FedAvg --------------------------------------

class ConfigFedAvgGenericData(ConfigFlowerFailuresData):
    """Parameters of Flower's FedAvg, see flwr.server.strategy.FedAvg."""
    inplace: bool = True


class ConfigFedAvgGeneric(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvgGeneric"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"

    name:   Literal["fedavggeneric"]
    config: ConfigFedAvgGenericData

    model_config = ConfigDict(extra="forbid")


class FedAvgGenericFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvg


# ------------------------------- FedAvgM -------------------------------------

class ConfigFedAvgMData(ConfigFlowerFailuresData):
    """Server-side momentum, see flwr.server.strategy.FedAvgM."""
    server_learning_rate: float = Field(default=1.0, gt=0)
    server_momentum:      float = Field(default=0.0, ge=0, lt=1)


class ConfigFedAvgM(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedAvgM"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"
    name:   Literal["fedavgm"]
    config: ConfigFedAvgMData
    model_config = ConfigDict(extra="forbid")


class FedAvgMFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvgM


# ------------------------- FedAdam / FedYogi / FedAdagrad ---------------------
# server-side adaptive optimizers; Flower defaults differ per class, kept as is

class ConfigFedAdamData(ConfigFlowerFailuresData):
    """Server-side Adam, see flwr.server.strategy.FedAdam."""
    eta:    float = Field(default=0.1,  gt=0)
    eta_l:  float = Field(default=0.1,  gt=0)
    beta_1: float = Field(default=0.9,  ge=0, lt=1)
    beta_2: float = Field(default=0.99, ge=0, lt=1)
    tau:    float = Field(default=1e-9, gt=0)


class ConfigFedAdam(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedAdam"
    PYBISCUS_GROUP: ClassVar[str] = "Server optimizers"
    name:   Literal["fedadam"]
    config: ConfigFedAdamData
    model_config = ConfigDict(extra="forbid")


class FedAdamFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAdam


class ConfigFedYogiData(ConfigFlowerFailuresData):
    """Server-side Yogi, see flwr.server.strategy.FedYogi."""
    eta:    float = Field(default=0.01,   gt=0)
    eta_l:  float = Field(default=0.0316, gt=0)
    beta_1: float = Field(default=0.9,    ge=0, lt=1)
    beta_2: float = Field(default=0.99,   ge=0, lt=1)
    tau:    float = Field(default=1e-3,   gt=0)


class ConfigFedYogi(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "FedYogi"
    PYBISCUS_GROUP: ClassVar[str] = "Server optimizers"
    name:   Literal["fedyogi"]
    config: ConfigFedYogiData
    model_config = ConfigDict(extra="forbid")


class FedYogiFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedYogi


class ConfigFedAdagradData(ConfigFlowerFailuresData):
    """Server-side Adagrad, see flwr.server.strategy.FedAdagrad."""
    eta:   float = Field(default=0.1,  gt=0)
    eta_l: float = Field(default=0.1,  gt=0)
    tau:   float = Field(default=1e-9, gt=0)


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
    inplace: bool = True


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
    beta: float = Field(default=0.2, ge=0, lt=0.5)


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
    num_malicious_clients: int = Field(default=0, ge=0)
    num_clients_to_keep:   int = Field(default=0, ge=0)


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
    num_malicious_clients: int = Field(default=0, ge=0)
    krum_to_keep:          int = Field(default=0, ge=0)


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
    """q-Fair FedAvg, see flwr.server.strategy.QFedAvg."""
    q_param:            float = Field(default=0.2, ge=0)
    qffl_learning_rate: float = Field(default=0.1, gt=0)


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
    min_completion_rate_fit:      float = Field(default=0.5, ge=0, le=1)
    min_completion_rate_evaluate: float = Field(default=0.5, ge=0, le=1)


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
    "fedavggeneric":       (FedAvgGenericFactory,       ConfigFedAvgGeneric),
    "fedavgm":             (FedAvgMFactory,             ConfigFedAvgM),
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
