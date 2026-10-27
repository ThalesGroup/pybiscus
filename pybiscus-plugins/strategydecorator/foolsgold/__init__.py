from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from foolsgold.foolsgolddecorator import ConfigFoolsGoldDecorator, FoolsGoldStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (FoolsGoldStrategyDecorator, ConfigFoolsGoldDecorator),
    ]
