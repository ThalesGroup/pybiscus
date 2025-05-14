
from typing import ClassVar, Literal, Union

from pydantic import BaseModel, ConfigDict
from pybiscus.interfaces.flower.flowerfitresultsaggregator import FlowerFitResultsAggregator

from flwr.common import (
    FitRes,
    Parameters,
    ndarrays_to_parameters as flw_ndarrays_to_parameters,
    parameters_to_ndarrays as flw_parameters_to_ndarrays,
)
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate as flw_aggregate



class ConfigFlowerFitResultsAggregatorUsingAverageData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigFlowerFitResultsAggregatorUsingAverage(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "Average"
    name:   Literal["average"]
    config: ConfigFlowerFitResultsAggregatorUsingAverageData
    model_config = ConfigDict(extra="forbid")


def pyb_aggregate_unweighted(results):
    """Aggregate model parameters with a simple average (non-weighted)."""

    if not results:
        return None

    # extract weights from parameters
    weights = [fit_res.parameters for _, fit_res in results]

    # weigths simple average
    n = len(weights)
    avg_weights = [ sum(layer) / n for layer in zip(*weights) ]

    return avg_weights


class FlowerFitResultsAggregatorUsingAverage(FlowerFitResultsAggregator):
    
    def __init__(self,empty_configuration):
        pass

    def aggregate( 
            self,
            server_round: int, 
            results: list[tuple[ClientProxy, FitRes]], 
            failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
            ) -> Parameters :
        """ Aggregate results : weighted average (with examples number as weight)"""
        
        tuples_ndarrays_weight = [ (flw_parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples) 
            for _, fit_res in results ]

        # handling of 📥🧬 results
        aggregated_results    = pyb_aggregate_unweighted(tuples_ndarrays_weight)

        # handling of 📤🧮🧬 aggregated result
        parameters_aggregated = flw_ndarrays_to_parameters(aggregated_results)

        return parameters_aggregated
