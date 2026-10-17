from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from fltrust.fltrustdecorator import ConfigFLTrustDecorator, FLTrustStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {"fltrust": FLTrustStrategyDecorator,}
    configs  = [ConfigFLTrustDecorator,]

    return registry, configs
