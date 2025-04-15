
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from src.ml.models.cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "cifar": LitCNN, }
    configs  = [ConfigModel_Cifar10]

    return registry, configs
