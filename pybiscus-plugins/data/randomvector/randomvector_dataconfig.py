from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import ConfigPartition, PartitionScheme, reject_former_fields


class RandomVectorTrainSet(BaseModel):
    """num_samples: generated examples; seed: order of the shuffled batches (random if unset);
    partition: this client's share of the generated examples; max_samples: at most this many"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    num_samples: int = Field(default=100, ge=1)
    batch_size:  int = Field(default=32, ge=1)
    shuffle:     bool = True
    drop_last:   bool = False
    seed:        Optional[int] = None
    partition:   Optional[ConfigPartition] = None
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _iid_only(self):
        # regression targets: no classes to spread (dirichlet) or sort (shards)
        if self.partition is not None and self.partition.scheme != PartitionScheme.iid:
            raise ValueError("random vectors have no classes: train.partition.scheme must be iid")
        return self


class RandomVectorEvalSet(BaseModel):
    """num_samples: generated examples; max_samples: at most this many"""

    num_samples: int = Field(default=50, ge=1)
    batch_size:  int = Field(default=32, ge=1)
    shuffle:     bool = False
    drop_last:   bool = False
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


class RandomVectorValSet(RandomVectorEvalSet):
    PYBISCUS_CONFIG: ClassVar[str] = "val"


class RandomVectorTestSet(RandomVectorEvalSet):
    PYBISCUS_CONFIG: ClassVar[str] = "test"


FORMER_FIELDS = {
    "num_samples": "train.num_samples (val and test used to get half of it: val.num_samples / test.num_samples)",
    "batch_size": "train.batch_size / val.batch_size / test.batch_size",
}


class ConfigRandomVector(BaseModel):
    """
    Configuration for generating a random vector dataset.

    Attributes:
        feature_dim (int): Number of features per sample (input dimensionality).
        seed (int): Random seed of the generated values (train, val and test get seed, seed + 1, seed + 2).
        train, val, test: number of generated samples and loader options of each set.

    Notes:
        - This configuration is useful for creating synthetic input data for testing models like linear regression.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    feature_dim: int = Field(default=1, ge=1)
    seed:        int = 42
    train:       RandomVectorTrainSet = RandomVectorTrainSet()
    val:         RandomVectorValSet = RandomVectorValSet()
    test:        RandomVectorTestSet = RandomVectorTestSet()

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data, FORMER_FIELDS)

# --- Pybiscus RandomVector configuration definition 

class ConfigData_RandomVector(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Random vector"

    name:   Literal["randomvector"]
    config: ConfigRandomVector

    model_config = ConfigDict(extra="forbid")
