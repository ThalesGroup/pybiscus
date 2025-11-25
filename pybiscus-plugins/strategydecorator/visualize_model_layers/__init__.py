
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from visualize_model_layers.visualizemodellayers import ConfigModelWeightVignetteStrategyDecorator, ModelWeightVignetteStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "visualizemodellayers" : ModelWeightVignetteStrategyDecorator,
        }
    configs  = [ConfigModelWeightVignetteStrategyDecorator, ]

    return registry, configs
