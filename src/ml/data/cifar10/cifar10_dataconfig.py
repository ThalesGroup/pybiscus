from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field

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

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    dir_train:   str = Field( default="${root_dir}/datasets/global_test/", description="the training data directory path" )
    dir_val:     str = Field( default = None, description="the validating data directory path" )
    #dir_test:    Optional[str] = Field( default = None, description="the testing data directory path" )
    dir_test:    str = Field( default = None, description="the testing data directory path" )
    batch_size:  int = Field( default = 32,   description="the batch size" )
    num_workers: int = Field( default = 0,    description="the number of workers for the DataLoaders" )

    model_config = ConfigDict(extra="forbid")

# --- Pybiscus Cifar10 configuration definition 

class ConfigData_Cifar10(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Cifar 10"

    name:   Literal["cifar"]
    config: ConfigCifar10Data

    model_config = ConfigDict(extra="forbid")

