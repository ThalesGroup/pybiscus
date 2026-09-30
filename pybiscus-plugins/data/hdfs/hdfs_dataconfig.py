from enum import Enum
from pathlib import Path
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import ConfigPartition, PartitionScheme, reject_former_fields

# HDFS log sequences (one per CSV line, event ids from 1): Deeplog learns to predict the next event
# of a window. The unit shared between clients or held out is the whole sequence: its windows
# overlap, and a sequence split between two sets would put the same events on both sides.


class HdfsTrainSet(BaseModel):
    """file: the training sequences (one per line); partition: this client's share of the
    sequences (iid only); seed: order of the shuffled batches"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    # the sample shipped with the plugin; a "${root_dir}" default would not be interpolated
    file: str = str(Path(__file__).parent / "train0.csv")
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = True
    drop_last: bool = False
    seed: Optional[int] = None
    partition: Optional[ConfigPartition] = None
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _iid_only(self):
        if self.partition is not None and self.partition.scheme != PartitionScheme.iid:
            raise ValueError("train.partition: sequences are shared iid only (dirichlet and shards split classes)")
        return self


class HdfsValSource(str, Enum):
    holdout = "holdout"   # a fraction of this client's training sequences
    file = "file"         # the sequences of val.file


class HdfsValSet(BaseModel):
    """source: holdout (fraction and seed of the client's sequences) or file"""

    PYBISCUS_CONFIG: ClassVar[str] = "val"

    source: HdfsValSource = HdfsValSource.holdout
    fraction: float = Field(default=0.1, gt=0, lt=1)
    seed: int = 42
    file: Optional[str] = None
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = False
    drop_last: bool = False
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _file_source(self):
        if self.source == HdfsValSource.file and not self.file:
            raise ValueError("val.source = file needs val.file")
        return self


class HdfsTestFormat(str, Enum):
    windows = "windows"     # the training format: next-event loss only
    sessions = "sessions"   # CSV "seq,label": labelled sessions, Deeplog's anomaly F1 (one batch)


class HdfsTestSet(BaseModel):
    """file: required to test (server side), no default: the former one was the training file;
    format: windows or sessions (batch_size unused: the F1 needs every session in one batch)"""

    PYBISCUS_CONFIG: ClassVar[str] = "test"

    file: Optional[str] = None
    format: HdfsTestFormat = HdfsTestFormat.windows
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = False
    drop_last: bool = False
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


HDFS_FORMER_FIELDS = {
    "train_file": "train.file",
    "val_file": "val.source: file + val.file",
    "test_file": "test.file (+ test.format: sessions for a seq,label file)",
    "batch_size": "train.batch_size / val.batch_size / test.batch_size",
    "window_size": "window",
}


class ConfigHDFS(BaseModel):
    """window: events seen before the one to predict"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    window: int = Field(default=10, ge=1)
    train: HdfsTrainSet = HdfsTrainSet()
    val: HdfsValSet = HdfsValSet()
    test: HdfsTestSet = HdfsTestSet()
    num_workers: int = 0

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data, HDFS_FORMER_FIELDS)

# --- Pybiscus HDFS configuration definition

class ConfigData_Hdfs(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "HDFS"

    name:   Literal["hdfs"]
    config: ConfigHDFS

    model_config = ConfigDict(extra="forbid")
