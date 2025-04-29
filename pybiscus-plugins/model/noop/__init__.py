
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from noop.lit_noop import LitNoop, ConfigModel_Noop

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "noop": LitNoop, }
    configs  = [ConfigModel_Noop]

    return registry, configs
