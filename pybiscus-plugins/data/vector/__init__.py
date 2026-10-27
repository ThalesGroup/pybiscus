
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from vector.vector_dataconfig import ConfigData_Vector
from vector.vector_datamodule import VectorLightningDataModule

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (VectorLightningDataModule, ConfigData_Vector),
    ]
