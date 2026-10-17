from typing import ClassVar, Literal, Optional

import lightning.pytorch as pl
import torchvision.transforms as transforms
from pydantic import BaseModel, ConfigDict, Field, model_validator
from torchvision.datasets import MNIST

from pybiscus.ml.datasplit import (
    ConfigPrivacySet, ConfigTestSet, ConfigTrainSet, ConfigTrustedSet, ConfigValSet, downloaded, limit, make_loader, privacy_loader,
    privacy_set, reject_former_fields, train_and_val_sets, trusted_loader, trusted_set,
)


class MnistTrainSet(ConfigTrainSet):
    dir: str = "${root_dir}/datasets/mnist/train/"
    batch_size: int = Field(default=64, ge=1)


class MnistValSet(ConfigValSet):
    dir: str = "${root_dir}/datasets/mnist/val/"
    batch_size: int = Field(default=64, ge=1)


class MnistTestSet(ConfigTestSet):
    dir: str = "${root_dir}/datasets/mnist/test/"
    batch_size: int = Field(default=64, ge=1)


class MnistPrivacySet(ConfigPrivacySet):
    dir: str = "${root_dir}/datasets/mnist/train/"
    batch_size: int = Field(default=64, ge=1)


class MnistTrustedSet(ConfigTrustedSet):
    dir: str = "${root_dir}/datasets/mnist/train/"


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
    privacy:
        optional, the examples a server-side privacy evaluation attacks (the train split)
    trusted:
        optional, the examples the server trains on to judge the clients' updates (fltrust)
    num_workers: int, optional
        the number of workers for the DataLoaders (default to 0)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    train: MnistTrainSet = MnistTrainSet()
    val: MnistValSet = MnistValSet()
    test: MnistTestSet = MnistTestSet()
    privacy: Optional[MnistPrivacySet] = None
    trusted: Optional[MnistTrustedSet] = None
    num_workers: int = Field(default=0, ge=0, description='processes loading the batches; 0: the main process')

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
    """MNIST from torchvision: 28 x 28 grey images of handwritten digits, 60,000 to train and 10,000 to
    test; the shared train, val, test, privacy and trusted sections choose the examples, the partition between
    clients and the loaders."""
    def __init__(self, train=None, val=None, test=None, privacy=None, trusted=None, num_workers: int = 0, **former_fields):
        super().__init__()
        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.train = MnistTrainSet.model_validate(train or {})
        self.val = MnistValSet.model_validate(val or {})
        self.test = MnistTestSet.model_validate(test or {})
        self.privacy = None if privacy is None else MnistPrivacySet.model_validate(privacy)
        self.data_privacy = None
        self.trusted = None if trusted is None else MnistTrustedSet.model_validate(trusted)
        self.data_trusted = None
        self.num_workers = num_workers
        self.transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]) # transforms.ToTensor()

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            train_full = self.train_source()
            official_val = lambda: downloaded(MNIST, self.val.dir, train=False, transform=self.transform)
            self.data_train, self.data_val = train_and_val_sets(train_full, official_val, self.train, self.val)

        if stage == "test" or stage is None:
            self.data_test = limit(downloaded(MNIST, self.test.dir, train=False, transform=self.transform), self.test.max_samples)
            if self.privacy is not None:
                self.data_privacy = privacy_set(self.train_source(self.privacy.dir), self.privacy)
            if self.trusted is not None:
                self.data_trusted = trusted_set(self.train_source(self.trusted.dir), self.trusted)

    def train_source(self, dir=None):
        """the official train split, in which the partitions and indices files pick their examples"""
        return downloaded(MNIST, dir or self.train.dir, train=True, transform=self.transform)

    def train_dataloader(self):
        return make_loader(self.data_train, self.train, self.num_workers, order_seed=self.train.seed)

    def val_dataloader(self):
        return make_loader(self.data_val, self.val, self.num_workers)

    def test_dataloader(self):
        return make_loader(self.data_test, self.test, self.num_workers)

    def privacy_dataloader(self):
        """None without a privacy section"""
        if self.data_privacy is None:
            return None
        return privacy_loader(self.data_privacy, self.privacy, self.num_workers)

    def trusted_dataloader(self):
        """None without a trusted section"""
        if self.data_trusted is None:
            return None
        return trusted_loader(self.data_trusted, self.trusted, self.num_workers)
