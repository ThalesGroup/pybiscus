from typing import Literal, ClassVar
from pydantic import BaseModel, ConfigDict

class ConfigRandomVector(BaseModel):

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
