from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.core.logger import LoggerFactory
from pybiscus.core.logger.webhooklogger.webhookloggerfactory import ConfigWebHookLoggerFactory, WebHookLoggerFactory


def get_modules_and_configs() -> List[Tuple[Type[LoggerFactory], Type[BaseModel]]]:

    return [
        (WebHookLoggerFactory, ConfigWebHookLoggerFactory),
    ]
