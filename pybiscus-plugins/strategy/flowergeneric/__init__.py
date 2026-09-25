
from typing import Dict, List, Tuple
from pydantic import BaseModel

from flowergeneric.flowergenericstrategy import ConfigFedAvgGeneric, FedAvgGenericFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "fedavggeneric": FedAvgGenericFactory, }
    configs  = [ConfigFedAvgGeneric,]

    return registry, configs
