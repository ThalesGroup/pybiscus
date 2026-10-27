
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.flower.flowerfitresultsaggregator.flowerfitresultsaggregatorusingweightedaverage.flowerfitresultsaggregatorusingweightedaverage import (
    ConfigFlowerFitResultsAggregatorUsingWeightedAverage, 
    FlowerFitResultsAggregatorUsingWeightedAverage,
)

from pybiscus.interfaces.flower.flowerfitresultsaggregator import FlowerFitResultsAggregator

def get_modules_and_configs() -> List[Tuple[Type[FlowerFitResultsAggregator], Type[BaseModel]]]:

    return [
        (FlowerFitResultsAggregatorUsingWeightedAverage, ConfigFlowerFitResultsAggregatorUsingWeightedAverage),
    ]
