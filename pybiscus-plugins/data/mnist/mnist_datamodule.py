from typing import ClassVar, Literal, Optional

import lightning.pytorch as pl
import torchvision.transforms as transforms
from pydantic import BaseModel, ConfigDict
from torch.utils.data import DataLoader
from torchvision.datasets import MNIST

import torch


class ConfigMnistData(BaseModel):
    """A Pydantic Model to validate the MnistLitDataModule config givent by the user.

    Attributes
    ----------
    dir_train: str
        path to the directory holding the training data
    dir_val: str
        path to the directory holding the validating data
    dir_test: str, optional
        path to the directory holding the testing data
    batch_size: int, optional
        the batch size (default to 64)
    num_workers: int, optional
        the number of workers for the DataLoaders (default to 2)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    dir_train: str = "${root_dir}/datasets/train/"
    dir_val: str = "${root_dir}/datasets/val/"
    dir_test: Optional[str] = "${root_dir}/datasets/test/"
    batch_size: int = 64
    num_workers: int = 2

    model_config = ConfigDict(extra="forbid")


class ConfigData_Mnist(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Mnist"

    name: Literal["mnist"]
    config: ConfigMnistData

    model_config = ConfigDict(extra="forbid")


class MnistLitDataModule(pl.LightningDataModule):
    def __init__(
        self,
        # root_dir,
        dir_train,
        dir_val,
        dir_test,
        batch_size,
        num_workers: int = 2,
    ):
        super().__init__()
        self.data_dir_train = dir_train
        self.data_dir_val = dir_val
        self.data_dir_test = dir_test
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]) # transforms.ToTensor()

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            self.data_train = MNIST(
                root=self.data_dir_train,
                train=True,
                download=True,
                transform=self.transform,
            )
            self.data_val = MNIST(
                root=self.data_dir_val,
                train=False,
                download=True,
                transform=self.transform,
            )

        if stage == "test" or stage is None:
            self.data_test = MNIST(
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
            #pin_memory=torch.cuda.is_available(),
        )

    def val_dataloader(self):
        return DataLoader(
            self.data_val,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=False,
            #pin_memory=torch.cuda.is_available(),
        )

    def test_dataloader(self):
        return DataLoader(
            self.data_test,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=False,
            #pin_memory=torch.cuda.is_available(),
        )
