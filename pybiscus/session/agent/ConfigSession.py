
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, ClassVar, Optional, Union, get_args

from pybiscus.core.schedule import ConfigSchedule
from pybiscus.core.seed import Seed
from pybiscus.flower_config.config_server import Robustness
from pybiscus.ml.datasplit import ConfigPartitionScheme
from pybiscus.plugin.registryloader import get_name_value_if_literal
from pybiscus.pydantic2xxx.pydantic2html import option_label

class FlowerServerConfiguration(BaseModel):

    class ServerProtocol(str, Enum):
        http  = "http"
        https = "https"

    class ServerListenTo(str, Enum):
        localhost     = "only localhost"
        wholeinternet = "the whole internet"

    PYBISCUS_CONFIG: ClassVar[str]  = "flower_server"

    server_host: str                 = Field(default="localhost", description="host name or address the clients reach the Flower server at")
    server_port: int                 = Field(default=3333, ge=1, le=65535, description="port of the Flower server")
    server_listen_to: ServerListenTo = Field(default=ServerListenTo.localhost, description="network the Flower server accepts clients from")
    server_protocol: ServerProtocol  = Field(default=ServerProtocol.http, description="https: the server and the clients get an ssl section to fill")
    
    model_config = ConfigDict(extra="forbid")
    
class ConfigSessionHoldout(BaseModel):
    """validation examples held out of each client's own training share (val.source: holdout; data
    plugins with a holdout: cifar, mnist, hdfs)"""

    fraction: float = Field(default=0.1, gt=0, lt=1, description="fraction of each client's training share held out for its validation")
    seed: Seed = Field(default=42, description="seed of the draw of the held-out examples")

    model_config = ConfigDict(extra="forbid")


def session_choices(names: list[str], confs) -> dict[str, str]:
    """registry name -> label shown in the session form, for each registered plugin"""

    union_type, *metadata = get_args(confs)
    # a union of a single config collapses to that config
    types = get_args(union_type) or (union_type,)
    # each config labelled by its own name: pairing the registry's names with the labels of the
    # configs that declare one shifted every label after a config without PYBISCUS_ALIAS
    labels = {get_name_value_if_literal(conf): option_label(conf) for conf in types}

    choices = {}
    for name in names:
        label = labels.get(name, name)
        # an Enum turns a repeated value into an alias of the first member: that option vanished
        if label in choices.values():
            label = f"{label} ({name})"
        choices[name] = label
    return choices


def make_session_model(models_confs, data: list[str], data_confs):

    enum_data  = Enum("SessionData",  session_choices(data, data_confs),     type=str)

    class ConfigSession(BaseModel):

        PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus session configuration"

        flower_server: FlowerServerConfiguration = Field(description="where the clients reach the Flower server")
        # the whole model and not only its plugin: models of different sizes cannot be averaged
        model:         models_confs = Field(description="model and hyperparameters of every participant, locked in their forms")  # pyright: ignore[reportInvalidTypeForm]
        data:          enum_data  = Field(default=next(iter(enum_data)), description="data plugin of every participant, locked in their forms")   # pyright: ignore[reportInvalidTypeForm]
        data_partition: Optional[ConfigPartitionScheme] = Field(default=None, description=
            "shares the training data between the clients registered at launch: the manager gives each one its share")
        data_holdout: Optional[ConfigSessionHoldout] = Field(default=None, description=
            "every client validates on a part of its own training share, whatever its form says")
        share_cpu_threads: bool = Field(default=True, description=
            "each client gets the cores of its machine divided by the clients on it: every PyTorch process takes all the cores otherwise")
        num_rounds: Optional[int] = Field(default=None, ge=1, description=
            "rounds of the session, set and locked in the server's form; unset: the server's form decides. "
            "Required with lower levels, which follow it round for round")
        min_clients: Optional[int] = Field(default=None, ge=1, description=
            "clients every round waits for; unset: the clients registered at launch (a confirmation states the risk of another number)")
        robustness: Robustness = Field(default=Robustness.none, description=
            "defense of the server against malicious clients, set and locked in its form")
        repeat: Optional[ConfigSchedule] = Field(default=None, description=
            "launch the session again at each deadline, once all its runs have ended: each one starts from the "
            "previous one's final weights, its clients read their new data, and it ends at once if none has any")
        record: bool = Field(default=False, description=
            "film the session from the manager's page (and the agents' run monitors) into a video, copied into the "
            "server's reports; the manager's machine needs uv, ffmpeg and Playwright's Chromium (docs/recording.md)")

    return ConfigSession
