
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.metricslogger.webhook.webhookmetricslogger import WebHookMetricsLogger

class ConfigWebHookMetricsLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    webhook_url: str = "http://localhost:5555/webhook/metrics"
    logger_id: str   = "🖧"

    model_config = ConfigDict(extra="forbid")


class ConfigWebHookMetricsLoggerFactory(BaseModel):

    name:   Literal["webhook"]

    PYBISCUS_ALIAS: ClassVar[str] = "WebHook"

    config: ConfigWebHookMetricsLoggerFactoryData

    model_config = ConfigDict(extra="forbid")


class WebHookMetricsLoggerFactory(MetricsLoggerFactory):

    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_metricslogger(self,reporting_path):

        return WebHookMetricsLogger(webhook_url=self.config.webhook_url,logger_id=self.config.logger_id)
