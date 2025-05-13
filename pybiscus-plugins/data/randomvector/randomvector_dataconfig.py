from typing import Literal, ClassVar
from pydantic import BaseModel, ConfigDict

class ConfigRandomVector(BaseModel):
    """
    Configuration for generating a random vector dataset.

    Attributes:
        num_samples (int): Number of data samples to generate.
        feature_dim (int): Number of features per sample (input dimensionality).
        seed (int): Random seed for reproducibility.
        batch_size (int): Size of data batches for training or evaluation.

    Notes:
        - This configuration is useful for creating synthetic input data for testing models like linear regression.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    num_samples: int = 100
    feature_dim: int = 1
    seed:        int = 42
    batch_size:  int = 32

# --- Pybiscus RandomVector configuration definition 

class ConfigData_RandomVector(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Random vector"

    name:   Literal["randomvector"]
    config: ConfigRandomVector

    model_config = ConfigDict(extra="forbid")
