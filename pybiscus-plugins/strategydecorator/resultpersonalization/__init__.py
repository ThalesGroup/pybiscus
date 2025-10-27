
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from resultpersonalization.resultpersonalizationstrategydecorator import PersonalizedResultStrategyDecorator, ConfigPersonalizationStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "resultpersonalization" : PersonalizedResultStrategyDecorator,
        }
    configs  = [ConfigPersonalizationStrategyDecorator, ]

    return registry, configs
