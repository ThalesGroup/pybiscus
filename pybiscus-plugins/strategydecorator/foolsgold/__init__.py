from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from foolsgold.foolsgolddecorator import ConfigFoolsGoldDecorator, FoolsGoldStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {"foolsgold": FoolsGoldStrategyDecorator,}
    configs  = [ConfigFoolsGoldDecorator,]

    return registry, configs
