from typing import Literal, Optional, ClassVar

import lightning.pytorch as pl
from pydantic import BaseModel, ConfigDict
from torch.utils.data import DataLoader
from src.ml.data.turbofan.turbofan_data import turbofan_dataset


class ConfigTurbofanData(BaseModel):
    """A Pydantic Model to validate the LitTurbofanDataModule config givent by the user.

    Attributes
    ----------
    data_path: str
        path to the directory holding the training data
    engines_list: list of int (among [52, 62, 2, 64, 69])
        list of engines to be used
    window : int
        window of data to feed the model
    batch_size: int, optional
        the batch size (default to 32)
    num_workers: int, optional
        the number of workers for the DataLoaders (default to 0)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    data_path: str = "turbofan.txt"
    engines_train_list: list[int] = [52]
    engines_val_list: list[int] = [64]
    engines_test_list: list[int] = [69]
    window: int = 20
    batch_size: int = 8
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")


class ConfigData_TurbofanData(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Turbofan"

    name: Literal["turbofan"]
    config: ConfigTurbofanData

    model_config = ConfigDict(extra="forbid")


class LitTurbofanDataModule(pl.LightningDataModule):
    def __init__(
        self,
        data_path,
        engines_train_list,
        engines_val_list,
        engines_test_list,
        window,
        batch_size,
        num_workers,
    ):
        super().__init__()
        self.data_path = data_path
        self.engines_train_list = engines_train_list
        self.engines_val_list = engines_val_list
        self.engines_test_list = engines_test_list
        self.window = window
        self.num_workers = num_workers
        self.batch_size = batch_size

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            self.data_train = turbofan_dataset(
                engines_list=self.engines_train_list,
                window=self.window,
                datapath=self.data_path,
            )
            self.data_val = turbofan_dataset(
                engines_list=self.engines_val_list,
                window=self.window,
                datapath=self.data_path,
            )
        if stage == "test" or stage is None:
            self.data_test = turbofan_dataset(
                engines_list=self.engines_test_list,
                window=self.window,
                datapath=self.data_path,
            )

    def train_dataloader(self):
        return DataLoader(
            self.data_train, batch_size=self.batch_size, shuffle=True, pin_memory=True
        )

    def val_dataloader(self):
        return DataLoader(
            self.data_val, batch_size=self.batch_size, shuffle=True, pin_memory=True
        )

    def test_dataloader(self):
        return DataLoader(
            self.data_test, batch_size=self.batch_size, shuffle=True, pin_memory=True
        )
