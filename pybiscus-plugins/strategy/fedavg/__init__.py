
from typing import Dict, List, Tuple
from pydantic import BaseModel
from flwr.server.strategy import Strategy

from fedavg.fedavgstrategy2 import FabricFedAvgStrategy2, ConfigFabricFedAvgStrategy2

def get_modules_and_configs() -> Tuple[Dict[str, Strategy], List[BaseModel]]:

    registry = { "fedavgextended": FabricFedAvgStrategy2, }
    configs  = [ConfigFabricFedAvgStrategy2,]

    return registry, configs
