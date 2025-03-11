from typing import Dict, Type

import lightning.pytorch as pl

from typing_extensions import Annotated, Union
from pydantic import Field

from src.ml.data.randomvector.randomvector_dataconfig import ConfigData_RandomVector
from src.ml.data.randomvector.randomvector_datamodule import RandomVectorLightningDataModule

from src.ml.data.cifar10.cifar10_dataconfig import ConfigData_Cifar10 
from src.ml.data.cifar10.cifar10_datamodule import CifarLightningDataModule 

from src.ml.models.cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )
from src.ml.data.turbofan.lit_turbofan_data import ( LitTurbofanDataModule, ConfigData_TurbofanData, )
from src.ml.models.lstm.lit_lstm_regressor import ( LitLSTMRegressor, ConfigModel_LSTM, )
from src.ml.models.linearregression.lit_linearregression import ( LitLinearRegression, ConfigModel_LinearRegression, )

#### --- Data Modules ---

datamodule_registry: Dict[str, Type[pl.LightningDataModule]] = {
    "randomvector": RandomVectorLightningDataModule,
    "cifar":        CifarLightningDataModule,
    "turbofan":     LitTurbofanDataModule,
}

DataConfig = Annotated[
    Union[
        ConfigData_RandomVector, 
        ConfigData_Cifar10, 
        ConfigData_TurbofanData
    ],
    Field(discriminator="name"),
]

#### --- Models ---

model_registry: Dict[str, Type[pl.LightningModule]] = {
    "linearregression": LitLinearRegression,
    "cifar": LitCNN, 
    "lstm":  LitLSTMRegressor
}

ModelConfig = Annotated[
    Union[
        ConfigModel_LinearRegression, 
        ConfigModel_Cifar10, 
        ConfigModel_LSTM
    ],
    Field(discriminator="name"),
]

