from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from serverdp.serverdpdecorator import (
    ConfigServerDPAdaptive,
    ConfigServerDPFixed,
    ServerDPAdaptiveStrategyDecorator,
    ServerDPFixedStrategyDecorator,
)

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (ServerDPFixedStrategyDecorator, ConfigServerDPFixed),
        (ServerDPAdaptiveStrategyDecorator, ConfigServerDPAdaptive),
    ]
