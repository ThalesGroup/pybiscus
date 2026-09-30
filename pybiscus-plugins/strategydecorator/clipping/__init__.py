from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from clipping.clippingdecorator import ClippingStrategyDecorator, ConfigClippingDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {"clipping": ClippingStrategyDecorator,}
    configs  = [ConfigClippingDecorator,]

    return registry, configs
