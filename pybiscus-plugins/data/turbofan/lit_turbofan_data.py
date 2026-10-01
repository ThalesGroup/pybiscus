from pathlib import Path
from typing import ClassVar, Literal, Optional

import lightning.pytorch as pl
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from torch.utils.data import DataLoader

import pybiscus.core.pybiscus_logger as logm
from pybiscus.ml.datasplit import SET_FIELDS, ConfigPartition, PartitionScheme, limit, make_loader, reject_former_fields
from turbofan.turbofan_data import TurbofanWindows, check_engines, normalization, read_engines


class TurbofanTrainSet(BaseModel):
    """engines: those whose cycles train the model; partition: this client's share of these
    engines, whole engines drawn at random (iid only); seed: order of the shuffled batches"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    engines: list[int] = Field(default_factory=lambda: [52, 62, 2], description='the engines whose cycles train the model; also set the normalization statistics')
    batch_size: int = Field(default=8, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=True, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    seed: Optional[int] = Field(default=None, description=SET_FIELDS["train_seed"])
    partition: Optional[ConfigPartition] = Field(default=None, description=SET_FIELDS["partition"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _engines_partition(self):
        if self.partition is None:
            return self
        if self.partition.scheme != PartitionScheme.iid:
            raise ValueError("train.partition: engines are shared iid only (dirichlet and shards split classes)")
        if self.partition.num_partitions > len(self.engines):
            raise ValueError(f"train.partition: {self.partition.num_partitions} partitions for {len(self.engines)} engines")
        return self


class TurbofanValSet(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "val"

    engines: list[int] = Field(default_factory=lambda: [64], description='the engines whose cycles validate the model')
    batch_size: int = Field(default=8, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=False, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")


class TurbofanTestSet(TurbofanValSet):
    PYBISCUS_CONFIG: ClassVar[str] = "test"

    engines: list[int] = Field(default_factory=lambda: [69])


TURBOFAN_FORMER_FIELDS = {
    "data_path": "file",
    "engines_train_list": "train.engines",
    "engines_val_list": "val.engines",
    "engines_test_list": "test.engines",
    "batch_size": "train.batch_size / val.batch_size / test.batch_size",
}


class ConfigTurbofanData(BaseModel):
    """NASA C-MAPSS turbofan engines (the plugin's turbofan.txt holds engines 52, 62, 2, 64, 69).
    file: the engines' cycles (CSV); window: cycles fed to the model, never across two engines;
    normalize: each feature standardized with the statistics of all the train section's engines,
    before partition, so that every client computes the same ones (the server's train.engines
    must be the clients'); rul_clip: cap on the remaining useful life to predict (unset: none)"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"
    # the server reads train.engines too: they set the normalization statistics
    PYBISCUS_SERVER_SECTIONS: ClassVar[tuple] = ("train", "test")

    # the file shipped with the plugin; a "${root_dir}" default would not be interpolated
    file: str = Field(default=str(Path(__file__).parent / "turbofan.txt"), description="the engines' cycles (CSV)")
    window: int = Field(default=20, ge=1, description='cycles fed to the model, never across two engines')
    normalize: bool = Field(default=True, description="each feature standardized with the statistics of the train section's engines")
    rul_clip: Optional[int] = Field(default=None, ge=1, description='cap on the remaining useful life to predict; none if unset')
    train: TurbofanTrainSet = Field(default=TurbofanTrainSet(), description='the engines the client trains on')
    val: TurbofanValSet = Field(default=TurbofanValSet(), description='the engines the client validates on')
    test: TurbofanTestSet = Field(default=TurbofanTestSet(), description="the engines of the final evaluation (the server's)")
    num_workers: int = Field(default=0, description='processes loading the batches; 0: the main process')

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data, TURBOFAN_FORMER_FIELDS)


class ConfigData_TurbofanData(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Turbofan"

    name: Literal["turbofan"]
    config: ConfigTurbofanData

    model_config = ConfigDict(extra="forbid")


def partition_engines(engines: list[int], partition: Optional[ConfigPartition]) -> list[int]:
    if partition is None:
        return list(engines)
    # the same seed on every client: disjoint shares without coordination
    order = np.random.default_rng(partition.seed).permutation(len(engines))
    share = np.array_split(order, partition.num_partitions)[partition.partition_id]
    return [engines[i] for i in sorted(share)]


class LitTurbofanDataModule(pl.LightningDataModule):

    def __init__(self, file=None, window: int = 20, normalize: bool = True, rul_clip=None,
                 train=None, val=None, test=None, num_workers: int = 0, **former_fields):
        super().__init__()
        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields, TURBOFAN_FORMER_FIELDS)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.file = file or ConfigTurbofanData.model_fields["file"].default
        self.window = window
        self.normalize = normalize
        self.rul_clip = rul_clip
        self.train = TurbofanTrainSet.model_validate(train or {})
        self.val = TurbofanValSet.model_validate(val or {})
        self.test = TurbofanTestSet.model_validate(test or {})
        self.num_workers = num_workers
        self.data_train = self.data_val = self.data_test = None

    def train_source(self):
        """the training engines, which the partitions share out whole"""
        return list(self.train.engines)

    def split_units(self, partition: Optional[ConfigPartition]) -> tuple[np.ndarray, None]:
        """engine numbers of a partition; no holdout: validation has its own engines"""
        return np.array(partition_engines(self.train.engines, partition)), None

    def setup(self, stage: Optional[str] = None):
        frame = read_engines(self.file)
        for section in ("train", "val", "test"):
            check_engines(frame, getattr(self, section).engines, section)
        stats = normalization(frame, self.train.engines) if self.normalize else None

        def windows(engines, section):
            return limit(TurbofanWindows(frame, engines, self.window, stats, self.rul_clip), section.max_samples)

        if stage == "fit" or stage is None:
            engines = partition_engines(self.train.engines, self.train.partition)
            self.data_train = windows(engines, self.train)
            self.data_val = windows(self.val.engines, self.val)
            logm.console.log(f"turbofan: training on engines {engines} ({len(self.data_train)} windows), "
                             f"validating on {self.val.engines} ({len(self.data_val)} windows)")
        if stage == "test" or stage is None:
            self.data_test = windows(self.test.engines, self.test)
            logm.console.log(f"turbofan: testing on engines {self.test.engines} ({len(self.data_test)} windows)")

    def train_dataloader(self) -> DataLoader:
        return make_loader(self.data_train, self.train, self.num_workers, order_seed=self.train.seed)

    def val_dataloader(self) -> DataLoader:
        return make_loader(self.data_val, self.val, self.num_workers)

    def test_dataloader(self) -> DataLoader:
        return make_loader(self.data_test, self.test, self.num_workers)
