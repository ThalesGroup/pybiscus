from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from evaluateonly.evaluateonlystrategydecorator import EvaluateOnlyStrategyDecorator, ConfigEvaluateOnlyStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (EvaluateOnlyStrategyDecorator, ConfigEvaluateOnlyStrategyDecorator),
    ]
