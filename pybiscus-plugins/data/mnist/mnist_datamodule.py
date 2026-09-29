from typing import ClassVar, Literal, Optional

import lightning.pytorch as pl
import torchvision.transforms as transforms
from pydantic import BaseModel, ConfigDict, Field, model_validator
from torchvision.datasets import MNIST

from pybiscus.ml.datasplit import ConfigTestSet, ConfigTrainSet, ConfigValSet, make_loader, reject_former_fields, train_and_val_sets


class MnistTrainSet(ConfigTrainSet):
    dir: str = "${root_dir}/datasets/mnist/train/"
    batch_size: int = Field(default=64, ge=1)


class MnistValSet(ConfigValSet):
    dir: str = "${root_dir}/datasets/mnist/val/"
    batch_size: int = Field(default=64, ge=1)


class MnistTestSet(ConfigTestSet):
    dir: str = "${root_dir}/datasets/mnist/test/"
    batch_size: int = Field(default=64, ge=1)


class ConfigMnistData(BaseModel):
    """A Pydantic Model to validate the MnistLitDataModule config givent by the user.

    Attributes
    ----------
    train:
        the training set: directory, loader options, indices file or partition between clients
    val:
        the validation set: source (official test split, holdout, indices file), loader options
    test:
        the testing set (required for the server): directory, loader options
    num_workers: int, optional
        the number of workers for the DataLoaders (default to 2)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    train: MnistTrainSet = MnistTrainSet()
    val: MnistValSet = MnistValSet()
    test: MnistTestSet = MnistTestSet()
    num_workers: int = 2

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data)


class ConfigData_Mnist(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Mnist"

    name: Literal["mnist"]
    config: ConfigMnistData

    model_config = ConfigDict(extra="forbid")


class MnistLitDataModule(pl.LightningDataModule):
    def __init__(self, train=None, val=None, test=None, num_workers: int = 2, **former_fields):
        super().__init__()
        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.train = MnistTrainSet.model_validate(train or {})
        self.val = MnistValSet.model_validate(val or {})
        self.test = MnistTestSet.model_validate(test or {})
        self.num_workers = num_workers
        self.transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]) # transforms.ToTensor()

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            train_full = MNIST(
                root=self.train.dir,
                train=True,
                download=True,
                transform=self.transform,
            )
            official_val = lambda: MNIST(
                root=self.val.dir,
                train=False,
                download=True,
                transform=self.transform,
            )
            self.data_train, self.data_val = train_and_val_sets(train_full, official_val, self.train, self.val)

        if stage == "test" or stage is None:
            self.data_test = MNIST(
                root=self.test.dir,
                train=False,
                download=True,
                transform=self.transform,
            )

    def train_dataloader(self):
        return make_loader(self.data_train, self.train, self.num_workers)

    def val_dataloader(self):
        return make_loader(self.data_val, self.val, self.num_workers)

    def test_dataloader(self):
        return make_loader(self.data_test, self.test, self.num_workers)
