from typing import List, Tuple, Type
from pydantic import BaseModel

from fedavgwithaggregator.fedavgwithaggregator import ConfigFedAvgWithAggregator, FedAvgWithAggregatorFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> List[Tuple[Type[FabricStrategyFactory], Type[BaseModel]]]:

    return [
        (FedAvgWithAggregatorFactory, ConfigFedAvgWithAggregator),
    ]
