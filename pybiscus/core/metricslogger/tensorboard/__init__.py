from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.core.metricslogger.tensorboard.tensorboardloggerfactory import TensorBoardLoggerFactory, ConfigTensorBoardLoggerFactory
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, MetricsLoggerFactory], List[BaseModel]]:

    registry = {"tensorboard": TensorBoardLoggerFactory, }
    configs  = [ConfigTensorBoardLoggerFactory, ]

    return registry, configs
