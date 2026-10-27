from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.metricslogger.webhook.webhookmetricsloggerfactory import ConfigWebHookMetricsLoggerFactory, WebHookMetricsLoggerFactory


def get_modules_and_configs() -> List[Tuple[Type[MetricsLoggerFactory], Type[BaseModel]]]:

    return [
        (WebHookMetricsLoggerFactory, ConfigWebHookMetricsLoggerFactory),
    ]
