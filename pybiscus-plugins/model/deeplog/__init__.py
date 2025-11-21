
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from deeplog.lit_deeplog import ( LitDeeplog, ConfigModel_hdfs, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "deeplog": LitDeeplog, }
    configs  = [ConfigModel_hdfs]

    return registry, configs
