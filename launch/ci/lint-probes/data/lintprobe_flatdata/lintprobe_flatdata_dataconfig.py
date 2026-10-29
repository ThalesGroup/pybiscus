from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import SET_FIELDS, ConfigPartition, PartitionScheme


class LintprobeFlatdataEvalSet(BaseModel):
    """examples generated for an evaluation"""

    num_samples: int = Field(default=50, ge=1, description="generated examples")
    batch_size: int = Field(default=32, ge=1, description=SET_FIELDS["batch_size"])
    shuffle: bool = Field(default=False, description=SET_FIELDS["shuffle"])
    drop_last: bool = Field(default=False, description=SET_FIELDS["drop_last"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")


class LintprobeFlatdataTrainSet(LintprobeFlatdataEvalSet):
    """the examples the client trains on"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    num_samples: int = Field(default=200, ge=1, description="generated training examples, shared between the clients")
    shuffle: bool = Field(default=True, description=SET_FIELDS["shuffle"])
    seed: Optional[int] = Field(default=None, description=SET_FIELDS["train_seed"])
    # a session's manager sets num_partitions and partition_id: each client gets its own share
    partition: Optional[ConfigPartition] = Field(default=None, description=SET_FIELDS["partition"])

    @model_validator(mode="after")
    def _iid_only(self):
        # regression targets: no classes to spread (dirichlet) or sort (shards)
        if self.partition is not None and self.partition.scheme != PartitionScheme.iid:
            raise ValueError("lintprobe_flatdata has no classes: train.partition.scheme must be iid")
        return self


class LintprobeFlatdataValSet(LintprobeFlatdataEvalSet):
    PYBISCUS_CONFIG: ClassVar[str] = "val"


# the server evaluates on it
class LintprobeFlatdataTestSet(LintprobeFlatdataEvalSet):
    PYBISCUS_CONFIG: ClassVar[str] = "test"


class ConfigLintprobeFlatdata(BaseModel):  # expect: data-sections
    """the settings of the lintprobe_flatdata data"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    feature_dim: int = Field(default=4, ge=1, description="features per example")
    seed: int = Field(default=42, description="seed of the generated values, the same for every client")
    train: LintprobeFlatdataTrainSet = Field(default=LintprobeFlatdataTrainSet(), description="the training examples")
    test: LintprobeFlatdataTestSet = Field(default=LintprobeFlatdataTestSet(), description="the test examples")

    model_config = ConfigDict(extra="forbid")


class ConfigData_LintprobeFlatdata(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "LintprobeFlatdata"

    # the registry key: what a configuration's `data: name:` gives
    name: Literal["lintprobe_flatdata"]
    config: ConfigLintprobeFlatdata

    model_config = ConfigDict(extra="forbid")
