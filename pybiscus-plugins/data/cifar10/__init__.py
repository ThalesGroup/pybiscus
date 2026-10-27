
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from cifar10.cifar10_dataconfig import ConfigData_Cifar10 
from cifar10.cifar10_datamodule import CifarLightningDataModule 

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (CifarLightningDataModule, ConfigData_Cifar10),
    ]
