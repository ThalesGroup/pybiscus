
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from fasterrcnn.lit_fasterrcnn import ( LitFasterRCNN, ConfigModel_FasterRCNN, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "fasterrcnn": LitFasterRCNN, }
    configs  = [ConfigModel_FasterRCNN]

    return registry, configs
