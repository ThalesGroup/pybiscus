from typing import List, Tuple, Type
from pydantic import BaseModel

from wandb_.wandbloggerfactory import WandbLoggerFactory, ConfigWandbLoggerFactory

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


def get_modules_and_configs() -> List[Tuple[Type[MetricsLoggerFactory], Type[BaseModel]]]:

    return [
        (WandbLoggerFactory, ConfigWandbLoggerFactory),
    ]
