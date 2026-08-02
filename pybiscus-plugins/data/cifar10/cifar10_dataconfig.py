from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field

class ConfigCifar10Data(BaseModel):
    """Pydantic Model used to validate the LightningDataModule config

    Attributes
    ----------
    dir_train:   str, optional = the training data directory path (required for clients)
    # dir_val:     str, optional = the validating data directory path (required for clients)
    dir_test:    str, optional = the testing data directory path (required for server)
    batch_size:  int, optional = the batch size (default to 32)
    num_workers: int, optional = the number of workers for the DataLoaders (default to 0)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    dir_train:   Optional[str] = "${root_dir}/datasets/train/"
    data_train_indices_path:   Optional[str] =None
    data_val_indices_path:   Optional[str] =None
    # dir_val:     Optional[str] = "${root_dir}/datasets/val/" # val can be suppressed, as there are only trainval and test for CIFAR10
    dir_test:    Optional[str] = "${root_dir}/datasets/test/"
    dir_privacy: Optional[str] = None
    batch_size:  int = 32
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")

# --- Pybiscus Cifar10 configuration definition 

class ConfigData_Cifar10(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Cifar 10"

    name:   Literal["cifar"]
    config: ConfigCifar10Data

    model_config = ConfigDict(extra="forbid")

