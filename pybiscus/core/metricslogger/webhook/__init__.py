from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.metricslogger.webhook.webhookmetricsloggerfactory import ConfigWebHookMetricsLoggerFactory, WebHookMetricsLoggerFactory


def get_modules_and_configs() -> Tuple[Dict[str, MetricsLoggerFactory], List[BaseModel]]:

    registry = {"webhook": WebHookMetricsLoggerFactory, }
    configs  = [ConfigWebHookMetricsLoggerFactory, ]

    return registry, configs
