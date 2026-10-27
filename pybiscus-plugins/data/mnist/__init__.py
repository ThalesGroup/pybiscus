
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from mnist.mnist_datamodule import ConfigData_Mnist, MnistLitDataModule

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (MnistLitDataModule, ConfigData_Mnist),
    ]
