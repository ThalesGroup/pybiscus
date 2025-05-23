from typing import Dict, List, Tuple
from pydantic import BaseModel

from wandb_.wandbloggerfactory import WandbLoggerFactory, ConfigWandbLoggerFactory

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, MetricsLoggerFactory], List[BaseModel]]:

    registry = {"wandb": WandbLoggerFactory, }
    configs  = [ConfigWandbLoggerFactory, ]

    return registry, configs
