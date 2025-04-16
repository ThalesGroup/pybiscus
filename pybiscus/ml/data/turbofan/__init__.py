
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from pybiscus.ml.data.turbofan.lit_turbofan_data import ( LitTurbofanDataModule, ConfigData_TurbofanData, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"turbofan":LitTurbofanDataModule,}
    configs  = [ConfigData_TurbofanData]

    return registry, configs
