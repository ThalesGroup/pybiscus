
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from visualize_model_layers.visualizemodellayers import ConfigModelWeightVignetteStrategyDecorator, ModelWeightVignetteStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (ModelWeightVignetteStrategyDecorator, ConfigModelWeightVignetteStrategyDecorator),
    ]
