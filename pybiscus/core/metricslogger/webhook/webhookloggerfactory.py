
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pybiscus.core.metricslogger.interface.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.metricslogger.webhook.webhooklogger import WebHookLogger

class ConfigWebHookLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    webhook_url: str = "http://localhost:9999/log_metrics"

    model_config = ConfigDict(extra="forbid")


class ConfigWebHookLoggerFactory(BaseModel):

    name:   Literal["webhook"]

    PYBISCUS_ALIAS: ClassVar[str] = "WebHook"

    config: ConfigWebHookLoggerFactoryData

    model_config = ConfigDict(extra="forbid")


class WebHookLoggerFactory(MetricsLoggerFactory):

    def __init__(self, root_dir, config):
        super().__init__()
        self.root_dir = root_dir
        self.config = config

    def get_logger(self):

        return [ WebHookLogger(root_dir=self.root_dir,webhook_url=self.config.webhook_url ) ]

