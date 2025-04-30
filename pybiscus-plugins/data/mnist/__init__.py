
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from mnist.mnist_datamodule import ConfigData_Mnist, MnistLitDataModule

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"mnist": MnistLitDataModule,}
    configs  = [ConfigData_Mnist]

    return registry, configs
