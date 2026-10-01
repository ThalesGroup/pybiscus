from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field

class ConfigiSAIDData(BaseModel):
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
    data_train_indices_path:   Optional[str] = Field(default=None, description='file of the indices of the training images')
    dir_val:   Optional[str] = Field(default="${root_dir}/datasets/val/", description='directory of the validation images')
    data_val_indices_path:   Optional[str] = Field(default=None, description='file of the indices of the validation images')
    dir_test:    Optional[str] = "${root_dir}/datasets/test/"
    dir_privacy: Optional[str] = Field(default=None, description='directory of the images a privacy evaluation attacks')
    batch_size:  int = 32
    num_workers: int = 0
    label_dict: Optional[dict] = Field(default=None, description='labels of the classes when they are not 0 .. n_classes - 1: {0: label0, 1: label1, ...}') # label dictionnary in case labels are note increasing integer from 0 to n_classes -1. {0: label0, 1: label1 etc.}

    model_config = ConfigDict(extra="forbid")

# --- Pybiscus iSAID configuration definition 

class ConfigData_iSAID(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "iSAID"

    name:   Literal["isaid"]
    config: ConfigiSAIDData

    model_config = ConfigDict(extra="forbid")

