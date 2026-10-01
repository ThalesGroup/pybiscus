from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.strategy.fedavg.fedavgstrategy import ConfigFedAvg, FedAvgFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "fedavg": FedAvgFactory, }
    configs  = [ConfigFedAvg]

    return registry, configs
