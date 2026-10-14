
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from iSAID.isaid_dataconfig import ConfigData_iSAID
from iSAID.isaid_datamodule import iSAIDLightningDataModule 

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"isaid": iSAIDLightningDataModule,}
    configs  = [ConfigData_iSAID]

    return registry, configs
