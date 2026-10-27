from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from omniscientalie.omniscientaliedecorator import ConfigOmniscientAlieDecorator, OmniscientAlieStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (OmniscientAlieStrategyDecorator, ConfigOmniscientAlieDecorator),
    ]
