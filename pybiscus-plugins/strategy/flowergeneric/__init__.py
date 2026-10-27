
from typing import List, Tuple, Type
from pydantic import BaseModel

from flowergeneric.flowergenericstrategy import FLOWER_STRATEGIES
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

def get_modules_and_configs() -> List[Tuple[Type[FabricStrategyFactory], Type[BaseModel]]]:

    return list(FLOWER_STRATEGIES.values())
