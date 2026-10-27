from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.core.metricslogger.tensorboard.tensorboardloggerfactory import TensorBoardLoggerFactory, ConfigTensorBoardLoggerFactory
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


def get_modules_and_configs() -> List[Tuple[Type[MetricsLoggerFactory], Type[BaseModel]]]:

    return [
        (TensorBoardLoggerFactory, ConfigTensorBoardLoggerFactory),
    ]
