
from typing import ClassVar, Literal, Union

import numpy as np
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



class ConfigFlowerFitResultsAggregatorUsingAverageData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigFlowerFitResultsAggregatorUsingAverage(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "Average"
    name:   Literal["average"]
    config: ConfigFlowerFitResultsAggregatorUsingAverageData
    model_config = ConfigDict(extra="forbid")


def pyb_aggregate_unweighted(ndarrays):
    """Aggregate model parameters with a simple average (non-weighted)."""

    if not ndarrays:
        return None

    # weigths simple average
    avg_weights = [np.mean(layer_group, axis=0) for layer_group in zip(*ndarrays)]

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
        
        ndarrays = [ flw_parameters_to_ndarrays(fit_res.parameters) 
            for _, fit_res in results ]

        logm.console.log(
            f"🔁 Round:{server_round} Average\n" +
            "\n".join(f"🆔{client.cid} ⚖️1" for client, _ in results)
        )

        # handling of 📥🧬 results
        aggregated_results    = pyb_aggregate_unweighted(ndarrays)

        # handling of 📤🧮🧬 aggregated result
        parameters_aggregated = flw_ndarrays_to_parameters(aggregated_results)

        return parameters_aggregated
