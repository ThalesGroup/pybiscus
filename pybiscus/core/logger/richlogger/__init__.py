from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.core.interfaces.logger import LoggerFactory
from pybiscus.core.logger.richlogger.richloggerfactory import RichLoggerFactory, ConfigRichLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, LoggerFactory], List[BaseModel]]:

    registry = {"rich": RichLoggerFactory, }
    configs  = [ConfigRichLoggerFactory, ]

    return registry, configs
