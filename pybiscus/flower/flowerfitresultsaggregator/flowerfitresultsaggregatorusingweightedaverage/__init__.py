
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.flowerfitresultsaggregator.flowerfitresultsaggregatorusingweightedaverage.flowerfitresultsaggregatorusingweightedaverage import (
    ConfigFlowerFitResultsAggregatorUsingWeightedAverage, 
    FlowerFitResultsAggregatorUsingWeightedAverage,
)

from pybiscus.interfaces.flower.flowerfitresultsaggregator import FlowerFitResultsAggregator

def get_modules_and_configs() -> Tuple[Dict[str, FlowerFitResultsAggregator], List[BaseModel]]:

    registry = {"weightedaverage": FlowerFitResultsAggregatorUsingWeightedAverage,}
    configs  = [ConfigFlowerFitResultsAggregatorUsingWeightedAverage,]

    return registry, configs
