from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from onnxmodel.lit_onnxmodel import LitOnnxModel, ConfigModel_OnnxModel

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitOnnxModel, ConfigModel_OnnxModel),
    ]
