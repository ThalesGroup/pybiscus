from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.core.logger import LoggerFactory
from pybiscus.core.logger.richlogger.richloggerfactory import RichLoggerFactory, ConfigRichLoggerFactory


def get_modules_and_configs() -> List[Tuple[Type[LoggerFactory], Type[BaseModel]]]:

    return [
        (RichLoggerFactory, ConfigRichLoggerFactory),
    ]
