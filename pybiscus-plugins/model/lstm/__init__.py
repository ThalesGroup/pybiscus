
from typing import List, Tuple, Type
import lightning.pytorch as pl
from pydantic import BaseModel

from lstm.lit_lstm_regressor import ( LitLSTMRegressor, ConfigModel_LSTM, )

def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:

    return [
        (LitLSTMRegressor, ConfigModel_LSTM),
    ]
