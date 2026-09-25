
from typing import Dict, List, Tuple
from pydantic import BaseModel

from flowergeneric.flowergenericstrategy import FLOWER_STRATEGIES
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { name: factory for name, (factory, _) in FLOWER_STRATEGIES.items() }
    configs  = [ config for _, config in FLOWER_STRATEGIES.values() ]

    return registry, configs
