
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitCNN, ConfigModel_Cifar10),
    ]
