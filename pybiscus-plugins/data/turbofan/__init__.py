
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from turbofan.lit_turbofan_data import ( LitTurbofanDataModule, ConfigData_TurbofanData, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (LitTurbofanDataModule, ConfigData_TurbofanData),
    ]
