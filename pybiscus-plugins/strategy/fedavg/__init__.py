
from typing import Dict, List, Tuple
from pydantic import BaseModel

from fedavg.fedavgstrategy2 import ConfigFabricFedAvgStrategy2, FabricFedAvgStrategyFactory2
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "fedavgextended": FabricFedAvgStrategyFactory2, }
    configs  = [ConfigFabricFedAvgStrategy2,]

    return registry, configs
