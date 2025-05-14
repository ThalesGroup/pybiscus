from logging import WARNING
from typing import Callable, Literal, Optional, Union, ClassVar

import flwr as fl
from flwr.common import (
    EvaluateRes,
    FitRes,
    MetricsAggregationFn,
    Parameters,
    Scalar,
    ndarrays_to_parameters as flw_ndarrays_to_parameters,
    parameters_to_ndarrays as flw_parameters_to_ndarrays,
)
from flwr.common.logger import log
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import (
    aggregate          as flw_aggregate,
    weighted_loss_avg  as flw_weighted_loss_avg,
)

from lightning.fabric import Fabric
from lightning.pytorch import LightningModule
from pydantic import BaseModel, ConfigDict

from pybiscus.flower.flowerfitresultsaggregator.flowerfitresultsaggregatorusingweightedaverage.flowerfitresultsaggregatorusingweightedaverage import FlowerFitResultsAggregatorUsingWeightedAverage
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory
from pybiscus.core.pybiscus_logger import pluggable_logger as console
from pybiscus.flower.utils_server import (
    evaluate_config    as pyb_evaluate_config, 
    fit_config         as pyb_fit_config, 
    get_evaluate_fn    as pyb_get_evaluate_fn, 
    weighted_average   as pyb_weighted_average,
)

WARNING_MIN_AVAILABLE_CLIENTS_TOO_LOW = """
Setting `min_available_clients` lower than `min_fit_clients` or
`min_evaluate_clients` can cause the server to fail when there are too few clients
connected to the server. `min_available_clients` must be set to a value larger
than or equal to the values of `min_fit_clients` and `min_evaluate_clients`.
"""

# #############################################################################################

# TODO: loggers
# there are 3 differents loggers used
# - flwr.common.logger.log
# - pybiscus.core.pybiscus_logger.pluggable_logger as console
# - Fabric.log

class ConfigFabricFedAvgStrategyData2(BaseModel):
    """    fraction_fit : float, optional
        Fraction of clients used during training. In case `min_fit_clients`
        is larger than `fraction_fit * available_clients`, `min_fit_clients`
        will still be sampled. Defaults to 1.0.
    fraction_evaluate : float, optional
        Fraction of clients used during validation. In case `min_evaluate_clients`
        is larger than `fraction_evaluate * available_clients`,
        `min_evaluate_clients` will still be sampled. Defaults to 1.0.
    min_fit_clients : int, optional
        Minimum number of clients used during training. Defaults to 2.
    min_evaluate_clients : int, optional
        Minimum number of clients used during validation. Defaults to 2.
    min_available_clients : int, optional
        Minimum number of total clients in the system. Defaults to 2.
    accept_failures : bool, optional
        Whether or not accept rounds containing failures. Defaults to True.
    inplace : bool (default: True)
        Enable (True) or disable (False) in-place aggregation of model updates.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    fraction_fit:          float = 1
    fraction_evaluate:     float = 1
    min_fit_clients:       int   = 2
    min_evaluate_clients:  int   = 2
    min_available_clients: int   = 2
    accept_failures:       bool  = True
    inplace:               bool  = True

    model_config = ConfigDict(extra="forbid")

# #############################################################################################

class ConfigFabricFedAvgStrategy2(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvgExtended"

    name:   Literal["fedavgextended"]
    config: ConfigFabricFedAvgStrategyData2

    model_config = ConfigDict(extra="forbid")

# #############################################################################################

class FabricFedAvgStrategy2(fl.server.strategy.FedAvg):
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

        fraction_fit: float = 1,
        fraction_evaluate: float = 1,
        min_fit_clients: int = 2,
        min_evaluate_clients: int = 2,
        min_available_clients: int = 2,
        evaluate_fn: Callable[[fl.common.NDArrays], Optional[tuple[float, float]]],
        on_fit_config_fn: Optional[Callable[[int], dict[str, Scalar]]] = None,
        on_evaluate_config_fn: Optional[Callable[[int], dict[str, Scalar]]] = None,
        accept_failures: bool = True,
        initial_parameters: Optional[Parameters] = None,
        fit_metrics_aggregation_fn: Optional[MetricsAggregationFn] = None,
        evaluate_metrics_aggregation_fn: Optional[MetricsAggregationFn] = None,
        inplace: bool = True,
    ) -> None:
        super().__init__(
            fraction_fit=fraction_fit,
            fraction_evaluate=fraction_evaluate,
            min_fit_clients=min_fit_clients,
            min_evaluate_clients=min_evaluate_clients,
            min_available_clients=min_available_clients,
            evaluate_fn=evaluate_fn,
            on_fit_config_fn=on_fit_config_fn,
            on_evaluate_config_fn=on_evaluate_config_fn,
            accept_failures= accept_failures,
            initial_parameters=initial_parameters,
            fit_metrics_aggregation_fn=fit_metrics_aggregation_fn,
            evaluate_metrics_aggregation_fn=evaluate_metrics_aggregation_fn,
            inplace=inplace,
        )

        self.model = model
        self.fabric = fabric

        # load the FlowerFitResultsAggregator from registry
        # flowerfitresultsaggregator_class = flowerfitresultsaggregator_registry()[flower_fit_results_aggregator.name]
        # self.flower_fit_results_aggregator = flowerfitresultsaggregator_class(**flower_fit_results_aggregator.config.model_dump())
        self.flower_fit_results_aggregator = FlowerFitResultsAggregatorUsingWeightedAverage(empty_configuration=True)

    # -------------------------------------------------------------------------

    def evaluate(self, server_round: int, parameters: Parameters) -> Optional[tuple[float, dict[str, Scalar]]]:
        """Evaluate model parameters using an evaluation function."""

        # No evaluation function provided
        if self.evaluate_fn is None:
            return None
        
        parameters_ndarrays = flw_parameters_to_ndarrays(parameters)

        eval_res = self.evaluate_fn(server_round, parameters_ndarrays, {})

        if eval_res is None:
            return None
        
        loss, metrics = eval_res
        
        for key, value in metrics.items():
            console.log(f"Test at round {server_round}, {key} is {value:.3f}")
            self.fabric.log(f"val_{key}_glob", value, step=server_round)

        return loss, metrics

    # -------------------------------------------------------------------------

    def aggregate_fit( self,
        server_round: int,
        results:      list[tuple[ClientProxy, FitRes]],
        failures:     list[Union[tuple[ClientProxy, FitRes], BaseException]],
    ) -> tuple[Optional[Parameters], dict[str, Scalar]]:
        """Aggregate fit results using weighted average."""

        if not results:
            return None, {}
        
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}

        # # Aggregate results : weighted average (with examples number as weight)
        # tuples_ndarrays_weight = [ (flw_parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples) 
        #     for _, fit_res in results ]
        # # TODO: add optional handling of 📥🧬 results
        # aggregated_results    = flw_aggregate(tuples_ndarrays_weight)
        # # TODO: add optional handling of 📤🧮🧬 aggregated result
        # parameters_aggregated = flw_ndarrays_to_parameters(aggregated_results)

        # Aggregate results
        parameters_aggregated = self.flower_fit_results_aggregator.aggregate( server_round, results, failures )

        # Aggregate custom metrics if aggregation fn was provided
        metrics_aggregated = {}

        if self.fit_metrics_aggregation_fn:

            tuples_weight_fitmetrics = [(res.num_examples, res.metrics) for _, res in results]
            # console.log(f"Fit metrics: {tuples_weight_fitmetrics}")
            # TODO: add optional handling of 📥📈 metrics

            for _, res in results:
                for key, value in res.metrics.items():

                    # default if cid is not found
                    cid = res.metrics.get("cid", f"client🔑_{key}")

                    self.fabric.log(f"fit_{key}_{cid}", value, step=server_round)

            metrics_aggregated = self.fit_metrics_aggregation_fn(tuples_weight_fitmetrics)
            # TODO: add optional handling of 📤🧮📈 aggregated metrics

        elif server_round == 1:  # Only log this warning once
            log(WARNING, "No fit_metrics_aggregation_fn provided")

        return parameters_aggregated, metrics_aggregated

    # -------------------------------------------------------------------------

    def aggregate_evaluate( self,
        server_round: int,
        results:      list[tuple[ClientProxy, EvaluateRes]],
        failures:     list[Union[tuple[ClientProxy, EvaluateRes], BaseException]],
    ) -> tuple[Optional[float], dict[str, Scalar]]:
        """Aggregate evaluation losses using weighted average."""

        if not results:
            return None, {}
        
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}

        # Aggregate loss
        tuples_weight_loss = [ (evaluate_res.num_examples, evaluate_res.loss) 
                for _, evaluate_res in results ]
        # TODO: add optional handling of 📥📉 losses
        loss_aggregated = flw_weighted_loss_avg(tuples_weight_loss)
        # TODO: add optional handling of 📤🧮📉 aggregated loss

        # Aggregate custom metrics if aggregation fn was provided
        metrics_aggregated = {}

        if self.evaluate_metrics_aggregation_fn:

            eval_metrics = [(res.num_examples, res.metrics) for _, res in results]
            # console.log(f"Val metrics: {eval_metrics}")
            # TODO: add optional handling of 📥📈 metrics

            for _, res in results:
                for key, value in res.metrics.items():
                    self.fabric.log(f"val_{key}_{res.metrics['cid']}", value, step=server_round)

            metrics_aggregated = self.evaluate_metrics_aggregation_fn(eval_metrics)
            # TODO: add optional handling of 📤🧮📈 aggregated metric

        elif server_round == 1:  # Only log this warning once
            log(WARNING, "No evaluate_metrics_aggregation_fn provided")

        return loss_aggregated, metrics_aggregated

# #############################################################################################
class FabricFedAvgStrategyFactory2(FabricStrategyFactory):

    def __init__(self,model,fabric,testset,initial_parameters,config,):
        self.model              = model
        self.fabric             = fabric
        self.testset            = testset
        self.initial_parameters = initial_parameters
        self.config             = config

    def get_strategy(self):

        return FabricFedAvgStrategy2(
            fit_metrics_aggregation_fn      = pyb_weighted_average,
            evaluate_metrics_aggregation_fn = pyb_weighted_average,
            model                           = self.model,
            fabric                          = self.fabric,
            evaluate_fn                     = pyb_get_evaluate_fn(testset=self.testset, model=self.model, fabric=self.fabric),
            on_fit_config_fn                = pyb_fit_config,
            on_evaluate_config_fn           = pyb_evaluate_config,
            initial_parameters              = self.initial_parameters,
            **self.config.model_dump()
        )
