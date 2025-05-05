from typing import Dict, List, Literal, Tuple
from pydantic import BaseModel

from pybiscus.core.metricslogger.webhook.webhookloggerfactory import ConfigWebHookLoggerFactory, WebHookLoggerFactory
from pybiscus.core.metricslogger.interface.metricsloggerfactory import MetricsLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, MetricsLoggerFactory], List[BaseModel]]:

    registry = {"webhook": WebHookLoggerFactory, }
    configs  = [ConfigWebHookLoggerFactory, ]

    return registry, configs
