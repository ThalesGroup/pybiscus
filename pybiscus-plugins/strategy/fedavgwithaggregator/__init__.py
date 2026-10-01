from typing import Dict, List, Tuple
from pydantic import BaseModel

from fedavgwithaggregator.fedavgwithaggregator import ConfigFedAvgWithAggregator, FedAvgWithAggregatorFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "fedavgwithaggregator": FedAvgWithAggregatorFactory, }
    configs  = [ConfigFedAvgWithAggregator]

    return registry, configs
