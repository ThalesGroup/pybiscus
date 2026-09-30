from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from serverdp.serverdpdecorator import (
    ConfigServerDPAdaptive,
    ConfigServerDPFixed,
    ServerDPAdaptiveStrategyDecorator,
    ServerDPFixedStrategyDecorator,
)

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "serverdpfixed":    ServerDPFixedStrategyDecorator,
        "serverdpadaptive": ServerDPAdaptiveStrategyDecorator,
        }
    configs  = [ConfigServerDPFixed, ConfigServerDPAdaptive]

    return registry, configs
