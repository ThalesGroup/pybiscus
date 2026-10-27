from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from mnistcnn.lit_mnist_cnn import LitMnistCNN, ConfigModel_MnistCNN

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitMnistCNN, ConfigModel_MnistCNN),
    ]
