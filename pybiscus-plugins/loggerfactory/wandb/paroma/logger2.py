from os.path import exists

import wandb

# from pytorch_lightning.callbacks import ModelCheckpoint
from lightning.pytorch.callbacks import ModelCheckpoint
from lightning.pytorch.loggers import WandbLogger
from omegaconf import OmegaConf


class Logger:
    def __init__(self, config: dict):
        login_config = config.get("login_config")  # Use .get() to avoid KeyError

        if login_config and exists(login_config):
            login = OmegaConf.load(login_config)
            wandb.login(**login["login"])
        else:
            wandb.login()

        self.wandb_logger = WandbLogger(**config.get("init_config", {}))
        self.ckpt_callback = ModelCheckpoint(**config.get("checkpoint_config", {}))

    def get_logger(self):
        return self.wandb_logger, self.ckpt_callback
