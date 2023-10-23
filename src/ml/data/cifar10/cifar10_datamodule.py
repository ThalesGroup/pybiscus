from typing import Literal, Optional

import lightning.pytorch as pl
import torchvision.transforms as transforms
from pydantic import BaseModel, ConfigDict
from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10


class ConfigCifar10Data(BaseModel):
    """A Pydantic Model to validate the CifarLitDataModule config givent by the user.

    Attributes
    ----------
    dir_train: str
        path to the directory holding the training data
    dir_val: str
        path to the directory holding the validating data
    dir_test: str, optional
        path to the directory holding the testing data
    batch_size: int, optional
        the batch size (default to 32)
    num_workers: int, optional
        the number of workers for the DataLoaders (default to 0)
    """

    dir_train: str
    dir_val: str
    dir_test: str = None
    batch_size: int = 32
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")


class ConfigData_Cifar10(BaseModel):
    name: Literal["cifar"]
    config: ConfigCifar10Data

    model_config = ConfigDict(extra="forbid")


class CifarLitDataModule(pl.LightningDataModule):
    def __init__(
        self,
        # root_dir,
        dir_train,
        dir_val,
        dir_test,
        batch_size,
        num_workers: int = 0,
    ):
        super().__init__()
        self.data_dir_train = dir_train
        self.data_dir_val = dir_val
        self.data_dir_test = dir_test
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            ]
        )

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            self.data_train = CIFAR10(
                root=self.data_dir_train,
                train=True,
                download=True,
                transform=self.transform,
            )
            self.data_val = CIFAR10(
                root=self.data_dir_val,
                train=False,
                download=True,
                transform=self.transform,
            )

        if stage == "test" or stage is None:
            self.data_test = CIFAR10(
                root=self.data_dir_test,
                train=False,
                download=True,
                transform=self.transform,
            )

    def train_dataloader(self):
        return DataLoader(
            self.data_train,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=True,
        )

    def val_dataloader(self):
        return DataLoader(
            self.data_val,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=False,
        )

    def test_dataloader(self):
        return DataLoader(
            self.data_test,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=False,
        )
