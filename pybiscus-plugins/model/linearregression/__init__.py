
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from linearregression.lit_linearregression import ( LitLinearRegression, ConfigModel_LinearRegression, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "linearregression": LitLinearRegression, }
    configs  = [ConfigModel_LinearRegression]

    return registry, configs
