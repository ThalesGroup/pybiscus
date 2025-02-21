from typing import Dict, Type

import lightning.pytorch as pl

from typing_extensions import Annotated, Union
from pydantic import Field

from src.ml.data.cifar10.cifar10_dataconfig import PybiscusConfigData_Cifar10 
from src.ml.data.cifar10.cifar10_datamodule import CifarLightningDataModule 

from src.ml.models.cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )
from src.ml.data.turbofan.lit_turbofan_data import ( LitTurbofanDataModule, ConfigData_TurbofanData, )
from src.ml.models.lstm.lit_lstm_regressor import ( LitLSTMRegressor, ConfigModel_LSTM, )

#### --- Models ---

model_registry: Dict[str, Type[pl.LightningModule]] = {
    "cifar": LitCNN, 
    "lstm":  LitLSTMRegressor
}

ModelConfig = Annotated[
    Union[ConfigModel_Cifar10, ConfigModel_LSTM],
    Field(discriminator="name"),
]

#### --- Data Modules ---

datamodule_registry: Dict[str, Type[pl.LightningDataModule]] = {
    "cifar":    CifarLightningDataModule,
    "turbofan": LitTurbofanDataModule,
}

DataConfig = Annotated[
    Union[PybiscusConfigData_Cifar10, ConfigData_TurbofanData],
    Field(discriminator="name"),
]
