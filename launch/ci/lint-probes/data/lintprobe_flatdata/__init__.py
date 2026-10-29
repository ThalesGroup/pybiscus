from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_flatdata.lintprobe_flatdata_dataconfig import ConfigData_LintprobeFlatdata
from lintprobe_flatdata.lintprobe_flatdata_datamodule import LintprobeFlatdataDataModule


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningDataModule], Type[BaseModel]]]:
    return [(LintprobeFlatdataDataModule, ConfigData_LintprobeFlatdata)]
