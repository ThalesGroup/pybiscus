
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from cifar10.cifar10_dataconfig import ConfigData_Cifar10 
from cifar10.cifar10_datamodule import CifarLightningDataModule 

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"cifar": CifarLightningDataModule,}
    configs  = [ConfigData_Cifar10]

    return registry, configs
