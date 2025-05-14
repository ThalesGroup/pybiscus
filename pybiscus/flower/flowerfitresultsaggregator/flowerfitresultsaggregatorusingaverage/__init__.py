
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.flowerfitresultsaggregator.flowerfitresultsaggregatorusingaverage.flowerfitresultsaggregatorusingaverage import (
    ConfigFlowerFitResultsAggregatorUsingAverage, 
    FlowerFitResultsAggregatorUsingAverage,
)

from pybiscus.interfaces.flower.flowerfitresultsaggregator import FlowerFitResultsAggregator

def get_modules_and_configs() -> Tuple[Dict[str, FlowerFitResultsAggregator], List[BaseModel]]:

    registry = {"average": FlowerFitResultsAggregatorUsingAverage,}
    configs  = [ConfigFlowerFitResultsAggregatorUsingAverage,]

    return registry, configs
