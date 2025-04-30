
from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import Annotated, ClassVar, Union, get_args

class NetworkConfiguration(BaseModel):
    class Protocol(str, Enum):
        http = "http"
        https = "https"

    class ServerListenTo(str, Enum):
        localhost = "only localhost"
        wholeinternet = "the whole internet"

    PYBISCUS_CONFIG: ClassVar[str] = "network"

    server_host: str = "localhost"
    server_port: int = 3333
    server_listen_to: ServerListenTo = ServerListenTo.localhost
    protocol: Protocol = Protocol.http
    
    model_config = ConfigDict(extra="forbid")
    
def make_session_model(models: list[str], models_confs, data: list[str], data_confs):

    union_type, *metadata = get_args(models_confs)
    models_types = get_args(union_type)
    models_labels = [m.PYBISCUS_ALIAS for m in models_types if hasattr(m, 'PYBISCUS_ALIAS')]

    union_type, *metadata = get_args(data_confs)
    data_types = get_args(union_type)
    data_labels = [d.PYBISCUS_ALIAS for d in data_types if hasattr(d, 'PYBISCUS_ALIAS')]

    enum_model = Enum("SessionModel", {k: v for k,v in zip(models, models_labels)}, type=str)
    enum_data = Enum("SessionData", {k: v for k,v in zip(data, data_labels)}, type=str)

    #enum_protocol = Enum("SessionSsl", {v: v for v in ["None", "SSL configuration"]}, type=str)

    class ConfigSession(BaseModel):

        network: NetworkConfiguration
        model: enum_model = next(iter(enum_model)) # pyright: ignore[reportInvalidTypeForm]
        data: enum_data = next(iter(enum_data)) # pyright: ignore[reportInvalidTypeForm]
        # ssl: enum_protocol = next(iter(enum_protocol)) # pyright: ignore[reportInvalidTypeForm]

    return ConfigSession
