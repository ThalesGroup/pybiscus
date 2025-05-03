from os.path import exists

import wandb

from lightning.pytorch.loggers import WandbLogger
from omegaconf import OmegaConf


class WdbLogger:
    def __init__(self):
        pass

    def login(self, login_path: str):
        if exists(login_path):
            login = OmegaConf.load(login_path)
            wandb.login(**login["login"])
        else:
            wandb.login()
            
    def get_logger(self, config: dict):
        return WandbLogger(**config)
    
wandb_logger = WdbLogger()