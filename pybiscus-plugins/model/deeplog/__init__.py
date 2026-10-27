
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from deeplog.lit_deeplog import ( LitDeeplog, ConfigModel_hdfs, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitDeeplog, ConfigModel_hdfs),
    ]
