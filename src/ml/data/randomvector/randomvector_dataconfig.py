from typing import Literal
from pydantic import BaseModel, ConfigDict

class ConfigRandomVector(BaseModel):
    """
    """

    num_samples: int = 100
    feature_dim: int = 1
    seed:        int = 42
    batch_size:  int = 32

# --- Pybiscus RandomVector configuration definition 

class ConfigData_RandomVector(BaseModel):
    name:   Literal["randomvector"]
    config: ConfigRandomVector

    model_config = ConfigDict(extra="forbid")
