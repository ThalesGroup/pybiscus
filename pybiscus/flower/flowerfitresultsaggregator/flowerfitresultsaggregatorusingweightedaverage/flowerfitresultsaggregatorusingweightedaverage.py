
from typing import ClassVar, Literal, Union

from pydantic import BaseModel, ConfigDict
from pybiscus.interfaces.flower.flowerfitresultsaggregator import FlowerFitResultsAggregator
import pybiscus.core.pybiscus_logger as logm

from flwr.common import (
    FitRes,
    Parameters,
    ndarrays_to_parameters as flw_ndarrays_to_parameters,
    parameters_to_ndarrays as flw_parameters_to_ndarrays,
)
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate as flw_aggregate



class ConfigFlowerFitResultsAggregatorUsingWeightedAverageData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigFlowerFitResultsAggregatorUsingWeightedAverage(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "WeightedAverage"
    name:   Literal["weightedaverage"]
    config: ConfigFlowerFitResultsAggregatorUsingWeightedAverageData
    model_config = ConfigDict(extra="forbid")



class FlowerFitResultsAggregatorUsingWeightedAverage(FlowerFitResultsAggregator):
    
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

        logm.console.log( f"WeightedAverage round:{server_round}\n" + "\n".join(f"🆔{client.cid}⚖️{fit_res.num_examples}" for client, fit_res in results) )

        # handling of 📥🧬 results
        aggregated_results    = flw_aggregate(tuples_ndarrays_weight)

        # handling of 📤🧮🧬 aggregated result
        parameters_aggregated = flw_ndarrays_to_parameters(aggregated_results)

        return parameters_aggregated
