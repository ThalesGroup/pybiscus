
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pybiscus.core.logger.interface.loggerfactory import LoggerFactory
from lightning.fabric.loggers import TensorBoardLogger

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


class TensorBoardLoggerFactory(LoggerFactory):

    def __init__(self):
        super().__init__()

    def get_logger( root_dir ):
        return (TensorBoardLogger(root_dir=root_dir), [])
