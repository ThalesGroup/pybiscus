from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.flower.strategy.fedavg.fedavgstrategy import ConfigFedAvg, FedAvgFactory
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> List[Tuple[Type[FabricStrategyFactory], Type[BaseModel]]]:

    return [
        (FedAvgFactory, ConfigFedAvg),
    ]
