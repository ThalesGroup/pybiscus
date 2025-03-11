from typing import Literal
from pydantic import BaseModel, ConfigDict

class ConfigCifar10Data(BaseModel):
    """Pydantic Model used to validate the LightningDataModule config

    Attributes
    ----------
    dir_train:   str           = the training data directory path
    dir_val:     str           = the validating data directory path
    dir_test:    str, optional = the testing data directory path
    batch_size:  int, optional = the batch size (default to 32)
    num_workers: int, optional = the number of workers for the DataLoaders (default to 0)
    """

    dir_train:   str
    dir_val:     str
    dir_test:    str = None
    batch_size:  int = 32
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")

# --- Pybiscus Cifar10 configuration definition 

class ConfigData_Cifar10(BaseModel):
    name:   Literal["cifar"]
    config: ConfigCifar10Data

    model_config = ConfigDict(extra="forbid")
