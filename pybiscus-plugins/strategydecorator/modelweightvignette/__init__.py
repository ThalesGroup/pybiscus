
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from modelweightvignette.modelweightvignette import ConfigModelWeightVignetteStrategyDecorator, ModelWeightVignetteStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "modelweightvignette" : ModelWeightVignetteStrategyDecorator,
        }
    configs  = [ConfigModelWeightVignetteStrategyDecorator, ]

    return registry, configs
