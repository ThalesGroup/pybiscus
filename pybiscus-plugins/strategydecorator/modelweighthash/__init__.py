
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from modelweighthash.modelweighthash import ConfigModelWeightHashStrategyDecorator, ModelWeighthashStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "modelweighthash" : ModelWeighthashStrategyDecorator,
        }
    configs  = [ConfigModelWeightHashStrategyDecorator, ]

    return registry, configs
