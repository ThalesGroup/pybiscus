from typing import Dict, List, Tuple
from pydantic import BaseModel

from wandb.wandbloggerfactory import ConfigWandbLoggerFactory, WandbLoggerFactory
from pybiscus.core.loggerfactory.interface.loggerfactory import LoggerFactory

def get_modules_and_configs() -> Tuple[Dict[str, LoggerFactory], List[BaseModel]]:

    registry = {"wandb": WandbLoggerFactory, }
    configs  = [ConfigWandbLoggerFactory, ]

    return registry, configs
