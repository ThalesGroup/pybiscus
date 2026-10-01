
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.interfaces.core.logger import LoggerFactory
from pybiscus.core.logger.webhooklogger.webhooklogger import WebHookLogger

class ConfigWebHookLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    webhook_url: str = Field(default="http://localhost:5555/webhook/logs", description="URL the log lines are posted to (the session manager's /webhook/logs)")
    logger_id: str   = Field(default="🖧", description='source tag of the posted lines')

    model_config = ConfigDict(extra="forbid")


class ConfigWebHookLoggerFactory(BaseModel):

    name:   Literal["webhook"]

    PYBISCUS_ALIAS: ClassVar[str] = "WebHook"

    config: ConfigWebHookLoggerFactoryData

    model_config = ConfigDict(extra="forbid")


class WebHookLoggerFactory(LoggerFactory):

    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_logger(self):

        return WebHookLogger(webhook_url=self.config.webhook_url,logger_id=self.config.logger_id )
