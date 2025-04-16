
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from pybiscus.ml.data.randomvector.randomvector_dataconfig import ConfigData_RandomVector
from pybiscus.ml.data.randomvector.randomvector_datamodule import RandomVectorLightningDataModule

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"randomvector": RandomVectorLightningDataModule,}
    configs  = [ConfigData_RandomVector]

    return registry, configs
