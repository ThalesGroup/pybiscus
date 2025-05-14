
from typing import Dict, List, Tuple
from pydantic import BaseModel

from fedavg3.fedavgstrategy3 import ConfigFabricFedAvgStrategy3, FabricFedAvgStrategyFactory3
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "fedavgextended3": FabricFedAvgStrategyFactory3, }
    configs  = [ConfigFabricFedAvgStrategy3,]

    return registry, configs
