
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from pybiscus.ml.models.lstm.lit_lstm_regressor import ( LitLSTMRegressor, ConfigModel_LSTM, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "lstm":  LitLSTMRegressor, }
    configs  = [ConfigModel_LSTM]

    return registry, configs
