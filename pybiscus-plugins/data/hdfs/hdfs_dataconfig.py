from typing import Literal, ClassVar, Optional
from pydantic import BaseModel, ConfigDict

class ConfigHDFS(BaseModel):
    """Pydantic Model used to validate the LightningDataModule config

    Attributes
    ----------
    train_file:   str, optional = the training data directory path (required for clients)
    test_file:     str, optional = the validating data directory path (required for clients)
    val_file:    str, optional = the testing data directory path (required for server)
    batch_size:  int, optional = the batch size (default to 32)
    window_size: int, optional = windows size for sequences (default to 10)
    """


    PYBISCUS_CONFIG: ClassVar[str] = "config"

    train_file:   Optional[str] = "./pybiscus-plugins/data/hdfs/train0.csv"
    test_file:     Optional[str] = "./pybiscus-plugins/data/hdfs/train0.csv"
    val_file:    Optional[str] = "./pybiscus-plugins/data/hdfs/train0.csv"
    batch_size:  int = 32
    window_size: int = 10

# --- Pybiscus HDFS configuration definition 

class ConfigData_Hdfs(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "HDFS"

    name:   Literal["hdfs"]
    config: ConfigHDFS

    model_config = ConfigDict(extra="forbid")
