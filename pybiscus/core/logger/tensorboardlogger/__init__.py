from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.core.logger.tensorboardlogger.tensorboardloggerfactory import TensorBoardLoggerFactory, ConfigTensorBoardLoggerFactory
from pybiscus.core.logger.interface.loggerfactory import LoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, LoggerFactory], List[BaseModel]]:

    registry = {"tensorboard": TensorBoardLoggerFactory, }
    configs  = [ConfigTensorBoardLoggerFactory, ]

    return registry, configs
