from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from rich.console import Console

from pybiscus.interfaces.core.logger import LoggerFactory

class ConfigRichLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")


class ConfigRichLoggerFactory(BaseModel):
    name:   Literal["rich"]
    PYBISCUS_ALIAS: ClassVar[str] = "RichLogger"
    config: ConfigRichLoggerFactoryData
    model_config = ConfigDict(extra="forbid")



class RichLoggerFactory(LoggerFactory):
    
    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_logger(self):

        return Console()
