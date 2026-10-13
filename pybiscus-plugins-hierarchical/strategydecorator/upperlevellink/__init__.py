from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from upperlevellink.upperlevellinkdecorator import UpperLevelLinkDecorator, ConfigUpperLevelLinkDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {"upperlevellink": UpperLevelLinkDecorator,}
    configs  = [ConfigUpperLevelLinkDecorator,]

    return registry, configs
