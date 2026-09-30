
from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import Annotated, ClassVar, Optional, Union, get_args

from pybiscus.ml.datasplit import ConfigPartitionScheme
from pybiscus.plugin.registryloader import get_name_value_if_literal

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
    
def session_choices(names: list[str], confs) -> dict[str, str]:
    """registry name -> label shown in the session form, for each registered plugin"""

    union_type, *metadata = get_args(confs)
    # a union of a single config collapses to that config
    types = get_args(union_type) or (union_type,)
    # each config labelled by its own name: pairing the registry's names with the labels of the
    # configs that declare one shifted every label after a config without PYBISCUS_ALIAS
    labels = {}
    for conf in types:
        name = get_name_value_if_literal(conf)
        labels[name] = getattr(conf, "PYBISCUS_ALIAS", name)

    choices = {}
    for name in names:
        label = labels.get(name, name)
        # an Enum turns a repeated value into an alias of the first member: that option vanished
        if label in choices.values():
            label = f"{label} ({name})"
        choices[name] = label
    return choices


def make_session_model(models: list[str], models_confs, data: list[str], data_confs):

    enum_model = Enum("SessionModel", session_choices(models, models_confs), type=str)
    enum_data  = Enum("SessionData",  session_choices(data, data_confs),     type=str)

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
