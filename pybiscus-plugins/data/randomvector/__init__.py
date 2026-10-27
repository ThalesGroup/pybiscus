
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from randomvector.randomvector_dataconfig import ConfigData_RandomVector
from randomvector.randomvector_datamodule import RandomVectorLightningDataModule

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (RandomVectorLightningDataModule, ConfigData_RandomVector),
    ]
