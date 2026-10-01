
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Field
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.metricslogger.webhook.webhookmetricslogger import WebHookMetricsLogger

class ConfigWebHookMetricsLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    webhook_url: str = Field(default="http://localhost:5555/webhook/metrics", description="URL the metrics are posted to (the session manager's /webhook/metrics)")
    logger_id: str   = Field(default="🖧", description='source tag of the posted metrics')

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
