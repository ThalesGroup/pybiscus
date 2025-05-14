
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from lightning.fabric.loggers import TensorBoardLogger
import pybiscus.core.pybiscus_logger as logm

class ConfigTensorBoardLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    subdir: str = "/experiments/node"

    model_config = ConfigDict(extra="forbid")


class ConfigTensorBoardLoggerFactory(BaseModel):

    name:   Literal["tensorboard"]

    PYBISCUS_ALIAS: ClassVar[str] = "TensorBoard"

    config: ConfigTensorBoardLoggerFactoryData

    model_config = ConfigDict(extra="forbid")

    # to emulate a dict
    def __getitem__(self, attName):
        return getattr(self, attName, None)


class TensorBoardLoggerFactory(MetricsLoggerFactory):

    def __init__(self, root_dir, config):
        super().__init__()
        self.root_dir = root_dir
        self.config = config

    def get_loggers(self):

        log_dir = self.root_dir + self.config.subdir
        logm.console.log(f"Allocating TensorBoardLoggerFactory(rootidr={log_dir})")

        return [TensorBoardLogger(root_dir=log_dir )]
