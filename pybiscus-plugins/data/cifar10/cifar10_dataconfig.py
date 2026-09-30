from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, model_validator

from pybiscus.ml.datasplit import ConfigPrivacySet, ConfigTestSet, ConfigTrainSet, ConfigValSet, reject_former_fields


class CifarTrainSet(ConfigTrainSet):
    dir: str = "${root_dir}/datasets/train/"


class CifarValSet(ConfigValSet):
    dir: str = "${root_dir}/datasets/val/"


class CifarTestSet(ConfigTestSet):
    dir: str = "${root_dir}/datasets/test/"


class CifarPrivacySet(ConfigPrivacySet):
    dir: str = "${root_dir}/datasets/train/"


class ConfigCifar10Data(BaseModel):
    """Pydantic Model used to validate the LightningDataModule config

    Attributes
    ----------
    train:       the training set: directory, loader options, indices file or partition between clients
    val:         the validation set: source (official test split, holdout, indices file), loader options
    test:        the testing set (required for the server): directory, loader options
    privacy:     optional, the examples a server-side privacy evaluation attacks (the train split)
    num_workers: int, optional = the number of workers for the DataLoaders (default to 0)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    train:       CifarTrainSet = CifarTrainSet()
    val:         CifarValSet = CifarValSet()
    test:        CifarTestSet = CifarTestSet()
    privacy:     Optional[CifarPrivacySet] = None
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data)

# --- Pybiscus Cifar10 configuration definition 

class ConfigData_Cifar10(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Cifar 10"

    name:   Literal["cifar"]
    config: ConfigCifar10Data

    model_config = ConfigDict(extra="forbid")
