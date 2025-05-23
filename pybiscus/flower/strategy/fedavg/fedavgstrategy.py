from collections import defaultdict
from logging import WARNING
from typing import Callable, Literal, Optional, Union, ClassVar

import flwr as fl
from flwr.common import (
    EvaluateRes,
    FitRes,
    MetricsAggregationFn,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays as flw_parameters_to_ndarrays,
)
from flwr.common.logger import log
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate, weighted_loss_avg
from lightning.fabric import Fabric
from lightning.pytorch import LightningModule
from pydantic import BaseModel, ConfigDict

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory
from pybiscus.flower.utils_server import evaluate_config, fit_config, get_evaluate_fn, weighted_average

WARNING_MIN_AVAILABLE_CLIENTS_TOO_LOW = """
Setting `min_available_clients` lower than `min_fit_clients` or
`min_evaluate_clients` can cause the server to fail when there are too few clients
connected to the server. `min_available_clients` must be set to a value larger
than or equal to the values of `min_fit_clients` and `min_evaluate_clients`.
"""

class ConfigFabricFedAvgStrategyData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    # fraction_fit: float = 1,
    # fraction_evaluate: float = 1,
    # min_fit_clients: int = 2,
    # min_evaluate_clients: int = 2,
    # min_available_clients: int = 2,

    min_fit_clients: int = 2

    model_config = ConfigDict(extra="forbid")


class ConfigFabricFedAvgStrategy(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvg"

    name:   Literal["fedavg"]
    config: ConfigFabricFedAvgStrategyData

    model_config = ConfigDict(extra="forbid")


class FabricFedAvgStrategy(fl.server.strategy.FedAvg):
    """A reimplementation of the FedAvg Strategy using Fabric.

    FabricFedAvgStrategy replaces the base version of Flower by a Fabric-powered version.
    Fabric allows to abstract the use of CPU/GPU, multiple hardwares, Float32/Float16 precision, and so on.
    A Fabric instance comes with a (TensorBoard) logger, allowing to log metrics and losses from the clients,
    using their cid as a marker.

    Attributes:
    -----------
    model (LightningModule): the model learnt the Federated way
    fabric (Fabric): a fabric instance, set up by the server
    evaluate_fn (Callable):
    """

    def __init__(
        self,
        *,
        model: LightningModule,
        fabric: Fabric,
        evaluate_fn: Callable[[fl.common.NDArrays], Optional[tuple[float, float]]],
        fit_metrics_aggregation_fn: Optional[MetricsAggregationFn] = None,
        evaluate_metrics_aggregation_fn: Optional[MetricsAggregationFn] = None,
        on_fit_config_fn: Optional[Callable[[int], dict[str, Scalar]]] = None,
        on_evaluate_config_fn: Optional[Callable[[int], dict[str, Scalar]]] = None,
        fraction_fit: float = 1,
        fraction_evaluate: float = 1,
        min_fit_clients: int = 2,
        min_evaluate_clients: int = 2,
        min_available_clients: int = 2,
        initial_parameters: Optional[Parameters] = None,
    ) -> None:
        super().__init__(
            evaluate_fn=evaluate_fn,
            fit_metrics_aggregation_fn=fit_metrics_aggregation_fn,
            evaluate_metrics_aggregation_fn=evaluate_metrics_aggregation_fn,
            fraction_fit=fraction_fit,
            fraction_evaluate=fraction_evaluate,
            min_fit_clients=min_fit_clients,
            min_evaluate_clients=min_evaluate_clients,
            min_available_clients=min_available_clients,
            on_fit_config_fn=on_fit_config_fn,
            on_evaluate_config_fn=on_evaluate_config_fn,
            initial_parameters=initial_parameters,
        )

        self.model = model
        self.fabric = fabric

    def evaluate(
        self, server_round: int, parameters: Parameters
    ) -> Optional[tuple[float, dict[str, Scalar]]]:
        """Evaluate model parameters using an evaluation function."""
        if self.evaluate_fn is None:
            # No evaluation function provided
            return None
        parameters_ndarrays = flw_parameters_to_ndarrays(parameters)
        eval_res = self.evaluate_fn(server_round, parameters_ndarrays, {})
        if eval_res is None:
            return None
        
        loss, metrics = eval_res

        emo = defaultdict(str)
        emo["loss"]     = "📉"
        emo["accuracy"] = "🎯"
        logmsg = ""

        for key, value in metrics.items():
            logmsg += f"{emo[key]} {key}={value:.3f} "
            self.fabric.log(f"val_{key}_glob", value, step=server_round)

        logm.console.log(f"🔁 Round {server_round} 🧪 Test {logmsg}")

        return loss, metrics

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
    ) -> tuple[Optional[Parameters], dict[str, Scalar]]:
        """Aggregate fit results using weighted average."""
        if not results:
            return None, {}
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}

        # Convert results
        tuples_ndarrays_weight = [ (flw_parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples) 
            for _, fit_res in results ]

        logm.console.log(
            f"🔁 Round:{server_round} WeightedAverage\n" +
            "\n".join(f"🆔{client.cid} ⚖️{fit_res.num_examples}" for client, fit_res in results)
        )

        parameters_aggregated = ndarrays_to_parameters(aggregate(tuples_ndarrays_weight))

        # Aggregate custom metrics if aggregation fn was provided
        metrics_aggregated = {}
        if self.fit_metrics_aggregation_fn:
            fit_metrics = [(res.num_examples, res.metrics) for _, res in results]
            # logm.console.log(f"Fit metrics: {fit_metrics}")
            for _, res in results:
                for key, value in res.metrics.items():
                    self.fabric.log(
                        f"fit_{key}_{res.metrics['cid']}", value, step=server_round
                    )
            metrics_aggregated = self.fit_metrics_aggregation_fn(fit_metrics)
        elif server_round == 1:  # Only log this warning once
            log(WARNING, "No fit_metrics_aggregation_fn provided")

        return parameters_aggregated, metrics_aggregated

    def aggregate_evaluate(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[Union[tuple[ClientProxy, EvaluateRes], BaseException]],
    ) -> tuple[Optional[float], dict[str, Scalar]]:
        """Aggregate evaluation losses using weighted average."""
        if not results:
            return None, {}
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}

        # Aggregate loss
        loss_aggregated = weighted_loss_avg(
            [
                (evaluate_res.num_examples, evaluate_res.loss)
                for _, evaluate_res in results
            ]
        )

        # Aggregate custom metrics if aggregation fn was provided
        metrics_aggregated = {}
        if self.evaluate_metrics_aggregation_fn:
            eval_metrics = [(res.num_examples, res.metrics) for _, res in results]
            # logm.console.log(f"Val metrics: {eval_metrics}")
            for _, res in results:
                for key, value in res.metrics.items():
                    self.fabric.log(
                        f"val_{key}_{res.metrics['cid']}", value, step=server_round
                    )
            metrics_aggregated = self.evaluate_metrics_aggregation_fn(eval_metrics)
        elif server_round == 1:  # Only log this warning once
            log(WARNING, "No evaluate_metrics_aggregation_fn provided")

        return loss_aggregated, metrics_aggregated


class FabricFedAvgStrategyFactory(FabricStrategyFactory):

    def __init__(self,model,fabric,testset,initial_parameters,config,):
        self.model=model
        self.fabric=fabric
        self.testset=testset
        self.initial_parameters=initial_parameters
        self.config=config

    def get_strategy(self):

        return FabricFedAvgStrategy(
            fit_metrics_aggregation_fn=weighted_average,
            evaluate_metrics_aggregation_fn=weighted_average,
            model=self.model,
            fabric=self.fabric,
            evaluate_fn=get_evaluate_fn(testset=self.testset, model=self.model, fabric=self.fabric),
            on_fit_config_fn=fit_config,
            on_evaluate_config_fn=evaluate_config,
            initial_parameters=self.initial_parameters,
            **self.config.model_dump()
        )
