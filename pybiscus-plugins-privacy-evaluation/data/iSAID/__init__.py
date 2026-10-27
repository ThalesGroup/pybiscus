
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from iSAID.isaid_dataconfig import ConfigData_iSAID
from iSAID.isaid_datamodule import iSAIDLightningDataModule 

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (iSAIDLightningDataModule, ConfigData_iSAID),
    ]
