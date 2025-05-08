from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.core.interfaces.logger import LoggerFactory
from pybiscus.core.logger.webhooklogger.webhookloggerfactory import ConfigWebHookLoggerFactory, WebHookLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, LoggerFactory], List[BaseModel]]:

    registry = {"webhook": WebHookLoggerFactory, }
    configs  = [ConfigWebHookLoggerFactory, ]

    return registry, configs
