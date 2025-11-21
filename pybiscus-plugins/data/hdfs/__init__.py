from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from hdfs.hdfs_dataconfig import  ConfigData_Hdfs
from hdfs.hdfs_datamodule import HDFSDataModule

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"hdfs": HDFSDataModule ,}
    configs  = [ConfigData_Hdfs]

    return registry, configs
