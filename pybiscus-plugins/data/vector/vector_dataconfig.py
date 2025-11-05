from typing import Literal, ClassVar
from pydantic import BaseModel, ConfigDict

class ConfigIntValueVector(BaseModel):
    """
    Configuration for generating a vector dataset.

    Attributes:
        num_samples (int): Number of data samples to generate.
        feature_dim (int): Number of features per sample (input dimensionality).
        batch_size (int): Size of data batches for training or evaluation.

    Notes:
        - This configuration is useful for creating synthetic input data for testing models like linear regression.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    num_samples: int = 10
    batch_size:  int = 10
    int_value:   int = 42

# --- Pybiscus Vector configuration definition 

class ConfigData_Vector(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Vector"

    name:   Literal["vector_"]
    config: ConfigIntValueVector

    model_config = ConfigDict(extra="forbid")
