from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from hdfs.hdfs_dataconfig import  ConfigData_Hdfs
from hdfs.hdfs_datamodule import HDFSDataModule

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:

    return [
        (HDFSDataModule, ConfigData_Hdfs),
    ]
