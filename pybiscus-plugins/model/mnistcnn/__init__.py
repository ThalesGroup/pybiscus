from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from mnistcnn.lit_mnist_cnn import LitMnistCNN, ConfigModel_MnistCNN

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "mnist_cnn": LitMnistCNN, }
    configs  = [ConfigModel_MnistCNN]

    return registry, configs
