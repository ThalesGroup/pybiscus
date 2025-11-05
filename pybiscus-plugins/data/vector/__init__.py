
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from vector.vector_dataconfig import ConfigData_Vector
from vector.vector_datamodule import VectorLightningDataModule

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"vector_": VectorLightningDataModule,}
    configs  = [ConfigData_Vector]

    return registry, configs
