
from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import Annotated, ClassVar, Optional, Union, get_args

from pybiscus.ml.datasplit import ConfigPartitionScheme

class FlowerServerConfiguration(BaseModel):

    class ServerProtocol(str, Enum):
        http  = "http"
        https = "https"

    class ServerListenTo(str, Enum):
        localhost     = "only localhost"
        wholeinternet = "the whole internet"

    PYBISCUS_CONFIG: ClassVar[str]  = "flower_server"

    server_host: str                 = "localhost"
    server_port: int                 = 3333
    server_listen_to: ServerListenTo = ServerListenTo.localhost
    server_protocol: ServerProtocol  = ServerProtocol.http
    
    model_config = ConfigDict(extra="forbid")
    
def make_session_model(models: list[str], models_confs, data: list[str], data_confs):

    union_type, *metadata = get_args(models_confs)
    models_types  = get_args(union_type)
    models_labels = [m.PYBISCUS_ALIAS for m in models_types if hasattr(m, 'PYBISCUS_ALIAS')]

    union_type, *metadata = get_args(data_confs)
    data_types  = get_args(union_type)
    data_labels = [d.PYBISCUS_ALIAS for d in data_types if hasattr(d, 'PYBISCUS_ALIAS')]

    enum_model = Enum("SessionModel", {k: v for k,v in zip(models, models_labels)}, type=str)
    enum_data  = Enum("SessionData",  {k: v for k,v in zip(data, data_labels)},     type=str)

    class ConfigSession(BaseModel):

        flower_server: FlowerServerConfiguration
        model:         enum_model = next(iter(enum_model))     # pyright: ignore[reportInvalidTypeForm]
        data:          enum_data  = next(iter(enum_data))      # pyright: ignore[reportInvalidTypeForm]
        # shares the training data between the clients registered when the session is launched:
        # the manager gives each one its partition_id (and the number of partitions)
        data_partition: Optional[ConfigPartitionScheme] = None
        # the manager gives each client the cores of its machine divided by the clients on it
        # (num_threads): each PyTorch process takes every core otherwise
        share_cpu_threads: bool = True

    return ConfigSession
