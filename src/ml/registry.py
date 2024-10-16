from typing_extensions import Annotated, Union
from pydantic import Field

from src.ml.data.cifar10.cifar10_datamodule import (
    CifarLitDataModule,
    ConfigData_Cifar10,
)
from src.ml.models.cnn.lit_cnn import LitCNN, ConfigModel_Cifar10


from src.ml.data.turbofan.lit_turbofan_data import (
    LitTurbofanDataModule,
    ConfigData_TurbofanData,
)
from src.ml.models.lstm.lit_lstm_regressor import LitLSTMRegressor, ConfigModel_LSTM

model_registry = {"cifar": LitCNN, "lstm": LitLSTMRegressor}

ModelConfig = Annotated[
    Union[ConfigModel_Cifar10, ConfigModel_LSTM],
    Field(discriminator="name"),
]

datamodule_registry = {
    "cifar": CifarLitDataModule,
    "turbofan": LitTurbofanDataModule,
}

DataConfig = Annotated[
    Union[ConfigData_Cifar10, ConfigData_TurbofanData],
    Field(discriminator="name"),
]
