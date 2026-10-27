
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from noop.lit_noop import LitNoop, ConfigModel_Noop

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitNoop, ConfigModel_Noop),
    ]
