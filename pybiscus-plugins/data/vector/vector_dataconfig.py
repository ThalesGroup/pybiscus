from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import SET_FIELDS, reject_former_fields


class VectorSet(BaseModel):
    """num_samples: examples of the set; max_samples: at most this many"""

    num_samples: int = Field(default=5, ge=1, description='examples of the set')
    batch_size:  int = Field(default=10, ge=1, description=SET_FIELDS["batch_size"])
    shuffle:     bool = Field(default=False, description=SET_FIELDS["shuffle"])
    drop_last:   bool = Field(default=False, description=SET_FIELDS["drop_last"])
    max_samples: Optional[int] = Field(default=None, ge=1, description=SET_FIELDS["max_samples"])

    model_config = ConfigDict(extra="forbid")


class VectorTrainSet(VectorSet):
    PYBISCUS_CONFIG: ClassVar[str] = "train"

    shuffle: bool = Field(default=True, description=SET_FIELDS["shuffle"])


class VectorValSet(VectorSet):
    PYBISCUS_CONFIG: ClassVar[str] = "val"


class VectorTestSet(VectorSet):
    PYBISCUS_CONFIG: ClassVar[str] = "test"


FORMER_FIELDS = {
    "num_samples": "train.num_samples / val.num_samples / test.num_samples (each set used to get half of it)",
    "batch_size": "train.batch_size / val.batch_size / test.batch_size",
}


class ConfigIntValueVector(BaseModel):
    """
    Configuration for generating a vector dataset.

    Attributes:
        int_value (int): the value of every example.
        train, val, test: number of examples and loader options of each set.

    Notes:
        - This configuration is useful for creating synthetic input data for testing models like linear regression.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    int_value: int = Field(default=42, description='the value of every example')
    train:     VectorTrainSet = Field(default=VectorTrainSet(), description='the training examples')
    val:       VectorValSet = Field(default=VectorValSet(), description='the validation examples')
    test:      VectorTestSet = Field(default=VectorTestSet(), description='the test examples')

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data, FORMER_FIELDS)

# --- Pybiscus Vector configuration definition 

class ConfigData_Vector(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Vector"

    name:   Literal["vector_"]
    config: ConfigIntValueVector

    model_config = ConfigDict(extra="forbid")
