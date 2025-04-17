
from typing import Dict, List, Tuple
from pydantic import BaseModel
from flwr.server.strategy import Strategy

from pybiscus.flower.strategy.fedavg.fedavgstrategy import FabricFedAvgStrategy, ConfigFabricFedAvgStrategy
from pybiscus.flower.strategy.fedavg.fedavgstrategy2 import FabricFedAvgStrategy2, ConfigFabricFedAvgStrategy2

def get_modules_and_configs() -> Tuple[Dict[str, Strategy], List[BaseModel]]:

    registry = {
                "fedavg": FabricFedAvgStrategy,
                "fedavg2": FabricFedAvgStrategy2,
                }
    configs  = [ConfigFabricFedAvgStrategy, ConfigFabricFedAvgStrategy2,]

    return registry, configs
