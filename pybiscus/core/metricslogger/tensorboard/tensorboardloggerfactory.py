
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory
from lightning.fabric.loggers import TensorBoardLogger
import pybiscus.core.pybiscus_logger as logm

class ConfigTensorBoardLoggerFactoryData(BaseModel):
    """The subdir is relative to the path defined by : 
server_run.reporting.basedir 
whose default is $(root_dir)/experiments/date-hour/"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    subdir: str = "tensorboard"

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

    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_metricslogger(self,reporting_path):

        from pybiscus.commands.app_server import ensure_dir_exists
        from pathlib import Path

        log_dir = Path(reporting_path) / Path(self.config.subdir)
        ensure_dir_exists(log_dir)

        logm.console.log(f"TensorBoardLogger allocated with 💾 root_dir={str(log_dir)}")
        return TensorBoardLogger(root_dir=str(log_dir) )
