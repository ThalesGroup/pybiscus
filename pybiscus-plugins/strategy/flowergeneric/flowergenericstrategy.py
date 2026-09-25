from collections import defaultdict
from functools import partial
from typing import ClassVar, Literal, Optional, Union

import flwr as fl
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict

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

    def get_strategy(self, clients_fit_local_epochs):
        strategy = with_fabric_logging(self.flower_strategy_class)(
            evaluate_fn=get_evaluate_fn(testset=self.testset, model=self.model, fabric=self.fabric),
            on_fit_config_fn=make_fit_config(clients_fit_local_epochs),
            on_evaluate_config_fn=evaluate_config,
            fit_metrics_aggregation_fn=partial(weighted_average, context="fit"),
            evaluate_metrics_aggregation_fn=partial(weighted_average, context="evaluate"),
            initial_parameters=self.initial_parameters,
            **self.config.model_dump(),
        )
        strategy.fabric = self.fabric
        return strategy


# ------------------------------- FedAvg --------------------------------------

class ConfigFedAvgGenericData(BaseModel):
    """Parameters of Flower's FedAvg, see flwr.server.strategy.FedAvg."""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    fraction_fit:          float = 1
    fraction_evaluate:     float = 1
    min_fit_clients:       int   = 2
    min_evaluate_clients:  int   = 2
    min_available_clients: int   = 2
    accept_failures:       bool  = True
    inplace:               bool  = True

    model_config = ConfigDict(extra="forbid")


class ConfigFedAvgGeneric(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvgGeneric"

    name:   Literal["fedavggeneric"]
    config: ConfigFedAvgGenericData

    model_config = ConfigDict(extra="forbid")


class FedAvgGenericFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvg
