from collections.abc import Mapping
from enum import Enum
from typing import List, Optional, ClassVar, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.flower_config.config_computecontext import ConfigServerComputeContext
from pybiscus.plugin.registries.logger_registry import LoggerConfig
from pybiscus.plugin.registries.model_registry import ModelConfig
from pybiscus.plugin.registries.data_registry import DataConfig
from pybiscus.plugin.registries.strategy_registry import StrategyConfig
from pybiscus.plugin.registries.strategydecorator_registry import StrategyDecoratorConfig
from pybiscus.plugin.registryloader import get_name_value_if_literal
import pybiscus.core.pybiscus_logger as logm

class ConfigSslServer(BaseModel):
    """A Pydantic Model to validate the ssl configuration given by the user.

    Attributes
    ----------
    root_certificate_path   = root certificate path
    server_certificate_path = server certificate path
    server_private_key_path = private key path
    """

    PYBISCUS_ALIAS: ClassVar[str] = "SSL configuration"

    root_certificate_path:   str = None
    server_certificate_path: str = None
    server_private_key_path: str = None

    model_config = ConfigDict(extra="forbid")


class ConfigSaveWeights(BaseModel):

    filename: str = Field(default="final_checkpoint.pt", description='file of the final weights, in the reporting directory')

    model_config = ConfigDict(extra="forbid")


class AxeKind(str, Enum):
    input  = "input"
    output = "output"

class OnnxAxe(BaseModel):

    name: str = Field(default="", description="name of the input or output in the ONNX model")
    kind: AxeKind = Field(default=AxeKind.input.value, description='whether the axis belongs to an input or an output of the model')
    dynamic: bool = Field(default=True, description='the size of this axis may change (the batch size, for instance)')

    model_config = ConfigDict(extra="forbid")

class ConfigServerOnnxExport(BaseModel):

    filename: str = Field(default="model.onnx", description='file of the exported model, in the reporting directory; the weights go to <file>.data beside it')
    axes: List[OnnxAxe] = Field(default=[], description='names and dynamic axes of the inputs and outputs; deduced from the model and the data if empty')
    # >= 18 requis avec l'exporteur torch dynamo (produit de l'opset 18 ; la reconversion
    # vers un opset inférieur, ex. 13, échoue)
    opset: int = Field(default=18, description='ONNX operator set: 18 or more with the dynamo exporter')
    post_validation: bool = Field(default=False, description="check the exported model with onnx and compare its outputs with PyTorch's on a sample (logged)")

    model_config = ConfigDict(extra="forbid")


class ConfigServerReporting(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "reporting"

    basedir: str = Field(default="${root_dir}/experiments", description="directory of the session's reports (logs, metrics, saved weights)")
    add_timestamp_in_path: bool = Field(default=True, description='one subdirectory per session, named after its start time (basedir/current links to the last one)')

    server_config_filename : str = Field(default="config_server.yml", description="file the server's configuration is saved to, in the reporting directory")

    save_on_train_end: Optional[ConfigSaveWeights] = Field(default=None, description='save the final weights of the global model')
    onnx_export:       Optional[ConfigServerOnnxExport] = Field(default=None, description='export the final global model to ONNX')

    model_config = ConfigDict(extra="forbid")

class ConfigServerRun(BaseModel):
    """A Pydantic Model to validate the server run configuration given by the user.

    Attributes
    ----------
    num_rounds: int    = the number of rounds for the FL session (>= 1).
    clients_fit_local_epochs = the number of local epochs performed by clients at each round (>= 1);
                         fit metrics describe the last local epoch, and when > 1 each epoch is also
                         reported as <metric>_epoch_<i>
    clients_configs    = list of paths to the configuration files used by all clients.
    save_on_train_end  = end of FL session model weights save flag
    seed               = seeds the server's random generators (initial weights, sampling of the
                         clients) for a reproducible session; random if unset
    """

    PYBISCUS_CONFIG: ClassVar[str] = "server_run"

    # >= 1: 0 local epochs crashed clients at their first fit (round 1, far from the cause),
    # 0 rounds silently trained nothing
    num_rounds:        int = Field(default=10, ge=1)
    clients_fit_local_epochs: int = Field(default=1, ge=1)
    client_configs:    list[str] = Field(default=[], description='configuration files of the clients, saved with the reports (command line sessions)')
    seed:              Optional[int] = None
    loggers:           list[LoggerConfig()] = Field(description="where the server's log lines go (console, the session manager's webhook...)")# pyright: ignore[reportInvalidTypeForm]
    reporting:         ConfigServerReporting= Field(description='where and what the server saves')
    model_config = ConfigDict(extra="forbid")


class ConfigFlowerServer(BaseModel):
    """A Pydantic Model to validate the server run configuration given by the user.

    Attributes
    ----------
    server_listen_address = the server listen address and port
    ssl                   = the flower server ssl configuration
    one_tera                = grpc config ( 1 Tb = 1_073_741_824 b)
    grpc_max_message_length = grpc config ( 1 Tb = 1_073_741_824 b)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "flower_server"

    listen_address:     str = Field(default='[::]:3333', description='address and port the Flower server listens on: [::1] the machine only, [::] every network')
    ssl:               Optional[ConfigSslServer] = None
    # one_tera: str = "1 Tb = 1073741824 b"
    # grpc_max_message_length : Optional[int] = None
    
    model_config = ConfigDict(extra="forbid")

# -----------------------------------------------

class Robustness(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    none = "none"
    safeguard = "safeguard"


Robustness.PYBISCUS_DESCRIPTIONS = {
    "none": "no defense against malicious clients",
    "safeguard": "updates clipped to 1.5 x the round's median norm, those above 1.7 x left out of the round: "
                 "stops attackers whose updates stand out, not those that stay within the honest clients' range",
}

# measured on cifar10, iid and dirichlet shares (docs/robust-aggregation.md): no cost without
# attacker, the conspicuous attackers rejected every round, honest clients at most 1.5 x the median
SAFEGUARD_DECORATOR = {"name": "clipping", "config": {"mode": "median", "median_factor": 1.5, "reject_factor": 1.7}}


def decorator_config_class(name: str):
    union_type = get_args(StrategyDecoratorConfig())[0]
    # a union of a single config collapses to that config
    for conf in get_args(union_type) or (union_type,):
        if get_name_value_if_literal(conf) == name:
            return conf
    return None


def same_value(found, expected) -> bool:
    # the forms send numbers as strings ("1.5"), a validated config holds enums
    return str(getattr(found, "value", found)) == str(expected)


def item_name(item):
    return item.get("name") if isinstance(item, Mapping) else getattr(item, "name", None)


def item_config(item):
    config = item.get("config") if isinstance(item, Mapping) else getattr(item, "config", None)
    if config is None or isinstance(config, Mapping):
        return config or {}
    return config.model_dump()


# the three FedAvg reimplementations merged into the core's fedavg (Flower's FedAvg, same parameters)
MERGED_STRATEGIES = {
    "fedavgextended": "use fedavg, which takes the same parameters",
    "fedavggeneric": "use fedavg, which is the same strategy",
    "fedavgextended3": "use fedavgwithaggregator, whose flower_fit_results_aggregator is now named aggregator",
}


class ConfigServerStrategy(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_strategy"

    pipeline: list[StrategyDecoratorConfig()] = Field(description='decorators around the strategy (metrics, saving, robustness...), the first one closest to the strategy')# pyright: ignore[reportInvalidTypeForm]
    strategy: StrategyConfig() = Field(description="how the clients' updates are aggregated")# pyright: ignore[reportInvalidTypeForm]
    robustness: Robustness = Field(default=Robustness.none, description=
        "defense against malicious clients, added to the pipeline (docs/robust-aggregation.md)")

    model_config = ConfigDict(extra="forbid")

    # said before the discriminated union's bare "does not match any of the expected tags"
    @model_validator(mode="before")
    @classmethod
    def refuse_merged_strategies(cls, data):
        strategy = data.get("strategy") if isinstance(data, Mapping) else None
        name = strategy.get("name") if isinstance(strategy, Mapping) else None
        if name in MERGED_STRATEGIES:
            raise ValueError(f"strategy {name} no longer exists: {MERGED_STRATEGIES[name]}")
        return data

    # a profile and not the decorator itself: a session preset can set a field, not add an item to
    # the pipeline, and a command line user writes one line
    @model_validator(mode="before")
    @classmethod
    def expand_robustness(cls, data):
        if not isinstance(data, Mapping) or not same_value(data.get("robustness"), Robustness.safeguard.value):
            return data
        pipeline = list(data.get("pipeline") or [])
        wanted = SAFEGUARD_DECORATOR["config"]
        present = [item for item in pipeline if item_name(item) == SAFEGUARD_DECORATOR["name"]]
        if present:
            # a configuration saved after the expansion holds it already
            config = item_config(present[0])
            if all(same_value(config.get(key), value) for key, value in wanted.items()):
                return data
            raise ValueError("robustness: safeguard sets the clipping decorator itself (median x 1.5, reject x 1.7): "
                             "remove the clipping of the pipeline, or keep it with robustness: none")
        clipping = decorator_config_class(SAFEGUARD_DECORATOR["name"])
        if clipping is None:
            raise ValueError("robustness: safeguard needs the clipping strategy decorator plugin, which is not loaded")
        # right after the decorators it must follow, else first (closest to the strategy)
        after = [index for index, item in enumerate(pipeline) if item_name(item) in getattr(clipping, "PYBISCUS_AFTER", ())]
        pipeline.insert(max(after) + 1 if after else 0, {"name": SAFEGUARD_DECORATOR["name"], "config": dict(wanted)})
        logm.console.log("🛡️ robustness safeguard: clipping decorator (median x 1.5, reject x 1.7) added to the pipeline")
        return {**data, "pipeline": pipeline}

    # a decorator config declares the decorators it cannot be combined with
    # (PYBISCUS_INCOMPATIBLE_WITH): refused at check rather than wrong results at run time
    @model_validator(mode="after")
    def check_compatible_decorators(self):
        names = [decorator.name for decorator in self.pipeline]
        for decorator in self.pipeline:
            for other in getattr(type(decorator), "PYBISCUS_INCOMPATIBLE_WITH", ()):
                others = names.count(other) - (other == decorator.name)
                if others > 0:
                    raise ValueError(f"pipeline: {decorator.name} cannot be combined with {other}")
            # PYBISCUS_AFTER: decorators to list before this one when present (the first of the list
            # is the closest to the strategy): one reading what the clients were sent must wrap the
            # one that changes it
            for other in getattr(type(decorator), "PYBISCUS_AFTER", ()):
                if other in names and names.index(other) > names.index(decorator.name):
                    raise ValueError(f"pipeline: {decorator.name} must come after {other}")
        return self


class ConfigServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    root_dir: str      = the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    logger: str        = the config for the logger.
    strategy           = arguments for the needed Strategy
    fabric             = keywords for the Fabric instance
    data               = keywords for the LightningDataModule used.
    model              = keywords for the LightningModule used
    """

    PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus server configuration"

    root_dir:               str = "${oc.env:PWD}"
    flower_server:          ConfigFlowerServer= Field(description='where the Flower server listens')
    server_run:             ConfigServerRun= Field(description='rounds, logs and reports of the session')
    server_compute_context: ConfigServerComputeContext= Field(description='hardware and metrics loggers of the server')
    server_strategy:        ConfigServerStrategy= Field(description='aggregation strategy, its decorators and the robustness profile')
    data:                   DataConfig() # pyright: ignore[reportInvalidTypeForm]
    model:                  ModelConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")
