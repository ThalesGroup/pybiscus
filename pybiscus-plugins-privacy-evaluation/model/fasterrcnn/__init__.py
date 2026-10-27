
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from fasterrcnn.lit_fasterrcnn import ( LitFasterRCNN, ConfigModel_FasterRCNN, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitFasterRCNN, ConfigModel_FasterRCNN),
    ]
