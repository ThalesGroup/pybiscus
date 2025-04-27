from os.path import exists
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

# import wandb

# from pytorch_lightning.callbacks import ModelCheckpoint
# from lightning.pytorch.callbacks import ModelCheckpoint
# from lightning.pytorch.loggers import WandbLogger
# from omegaconf import OmegaConf

from pybiscus.core.logger.interface.loggerfactory import LoggerFactory

class ConfigWandbLoggerFactoryData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    # rootdir: str = "${rootdir}/experiments/node"

    model_config = ConfigDict(extra="forbid")


class ConfigWandbLoggerFactory(BaseModel):

    name:   Literal["wandb"]

    PYBISCUS_ALIAS: ClassVar[str] = "WanDb"

    config: ConfigWandbLoggerFactoryData

    model_config = ConfigDict(extra="forbid")

    # to emulate a dict
    def __getitem__(self, attName):
        return getattr(self, attName, None)


class WandbLoggerFactory(LoggerFactory):

    pass
    # def __init__(self, config: dict):
    #     login_config = config.get("login_config")  # Use .get() to avoid KeyError

    #     if login_config and exists(login_config):
    #         login = OmegaConf.load(login_config)
    #         wandb.login(**login["login"])
    #     else:
    #         wandb.login()

    #     self.wandb_logger = WandbLogger(**config.get("init_config", {}))
    #     self.ckpt_callback = ModelCheckpoint(**config.get("checkpoint_config", {}))

    # def login(self, login_path: str):
    #     if exists(login_path):
    #         login = OmegaConf.load(login_path)
    #         wandb.login(**login["login"])
    #     else:
    #         wandb.login()

    # def get_logger(self):
    #     return self.wandb_logger, self.ckpt_callback
    
    # def get_logger(self, config: dict):
    #     return WandbLogger(**config)
