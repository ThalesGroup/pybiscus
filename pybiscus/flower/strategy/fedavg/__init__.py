
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.strategy.fedavg.fedavgstrategy import ConfigFabricFedAvgStrategy, FabricFedAvgStrategyFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = {"fedavg": FabricFedAvgStrategyFactory,}
    configs  = [ConfigFabricFedAvgStrategy,]

    return registry, configs
