
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
from filewritingdecorator.filewritingdecorator import FileWritingDecorator, ConfigFileWritingDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "filewriting": FileWritingDecorator,
        }
    configs  = [ConfigFileWritingDecorator,]

    return registry, configs
