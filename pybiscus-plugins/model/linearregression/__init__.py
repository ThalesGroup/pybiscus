
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from linearregression.lit_linearregression import ( LitLinearRegression, ConfigModel_LinearRegression, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitLinearRegression, ConfigModel_LinearRegression),
    ]
