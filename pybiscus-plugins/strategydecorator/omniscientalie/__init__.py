from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from omniscientalie.omniscientaliedecorator import ConfigOmniscientAlieDecorator, OmniscientAlieStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {"omniscientalie": OmniscientAlieStrategyDecorator,}
    configs  = [ConfigOmniscientAlieDecorator,]

    return registry, configs
