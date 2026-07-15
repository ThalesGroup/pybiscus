
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from unet.lit_unet import ( LitUnet, ConfigModel_Unet, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "unet": LitUnet, }
    configs  = [ConfigModel_Unet]

    return registry, configs
