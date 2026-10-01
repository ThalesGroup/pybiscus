from enum import Enum
from pathlib import Path
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import SET_FIELDS, ConfigPartition, PartitionScheme, reject_former_fields

# HDFS log sequences (one per CSV line, event ids from 1): Deeplog learns to predict the next event
# of a window. The unit shared between clients or held out is the whole sequence: its windows
# overlap, and a sequence split between two sets would put the same events on both sides.


class HdfsTrainSet(BaseModel):
    """file: the training sequences (one per line); partition: this client's share of the
    sequences (iid only); seed: order of the shuffled batches"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    # the sample shipped with the plugin; a "${root_dir}" default would not be interpolated
    file: str = Field(default=str(Path(__file__).parent / "train0.csv"), description='the training sequences, one per line')
    batch_size: int = Field(default=32, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=True, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    seed: Optional[int] = Field(default=None, description=SET_FIELDS["train_seed"])
    partition: Optional[ConfigPartition] = Field(default=None, description=SET_FIELDS["partition"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _iid_only(self):
        if self.partition is not None and self.partition.scheme != PartitionScheme.iid:
            raise ValueError("train.partition: sequences are shared iid only (dirichlet and shards split classes)")
        return self


class HdfsValSource(str, Enum):
    holdout = "holdout"
    file = "file"


HdfsValSource.PYBISCUS_DESCRIPTIONS = {
    "holdout": "a fraction of this client's training sequences, left out of its training",
    "file": "the sequences of val.file",
}


class HdfsValSet(BaseModel):
    """source: holdout (fraction and seed of the client's sequences) or file"""

    PYBISCUS_CONFIG: ClassVar[str] = "val"

    source: HdfsValSource = Field(default=HdfsValSource.holdout, description='where the validation sequences come from')
    fraction: float = Field(default=0.1, gt=0, lt=1, description="share of the client's training sequences held out (source: holdout)")
    seed: int = Field(default=42, description='draw of the held-out sequences (source: holdout)')
    file: Optional[str] = Field(default=None, description='the validation sequences (source: file)')
    batch_size: int = Field(default=32, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=False, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _file_source(self):
        if self.source == HdfsValSource.file and not self.file:
            raise ValueError("val.source = file needs val.file")
        return self


class HdfsTestFormat(str, Enum):
    windows = "windows"
    sessions = "sessions"


HdfsTestFormat.PYBISCUS_DESCRIPTIONS = {
    "windows": "the training format: next-event loss only",
    "sessions": 'CSV "seq,label": labelled sessions, scored by Deeplog\'s anomaly F1 (in one batch)',
}


class HdfsTestSet(BaseModel):
    """file: required to test (server side), no default: the former one was the training file;
    format: windows or sessions (batch_size unused: the F1 needs every session in one batch)"""

    PYBISCUS_CONFIG: ClassVar[str] = "test"

    file: Optional[str] = Field(default=None, description='the test sequences: required to test (server side)')
    format: HdfsTestFormat = Field(default=HdfsTestFormat.windows, description='how the test file is read and scored')
    batch_size: int = Field(default=32, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=False, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

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

    window: int = Field(default=10, ge=1, description='events the model sees before the one it predicts')
    train: HdfsTrainSet = Field(default=HdfsTrainSet(), description='the sequences the client trains on')
    val: HdfsValSet = Field(default=HdfsValSet(), description='the sequences the client validates on')
    test: HdfsTestSet = Field(default=HdfsTestSet(), description="the sequences of the final evaluation (the server's)")
    num_workers: int = Field(default=0, description='processes loading the batches; 0: the main process')

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
