from enum import Enum
from typing import Optional, ClassVar
from typing_extensions import Annotated

import torch
from pydantic import BaseModel, ConfigDict

from pybiscus.flower_config.config_computecontext import ConfigClientComputeContext
from pybiscus.plugin.registries.client_registry import ClientConfig
from pybiscus.plugin.registries.model_registry import ModelConfig
from pybiscus.plugin.registries.data_registry import DataConfig

torch.backends.cudnn.enabled = True


ConfigModel = Annotated[int, lambda x: x > 0]


class ConfigSslClient(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    Attributes
    ----------
    secure_cnx: 
        Enables HTTPS connection when true, default value being false
        using system certificates if root_certificate is None

    root_certificate:
        he PEM-encoded root certificates path
    """

    PYBISCUS_ALIAS: ClassVar[str] = "SSL configuration"

    secure_cnx: bool
    root_certificate: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class OptimizerState(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    reset = "reset"   # a new optimizer (and schedulers) at every round, as in standard FedAvg
    keep  = "keep"    # the state of the previous rounds (momentum, Adam moments) is kept


class ConfigClientRun(BaseModel):
    """A Pydantic Model to validate the server run configuration given by the user.

    Attributes
    ----------
    cid: int = client identifier
    optimizer_state: reset | keep = whether the optimizer starts afresh at every round (default) or
        keeps its state (momentum, Adam moments) from the previous rounds, computed on other weights
    """

    PYBISCUS_CONFIG: ClassVar[str] = "client_run"

    cid: int            = 1
    pre_train_val: bool = False
    optimizer_state: OptimizerState = OptimizerState.reset

    model_config = ConfigDict(extra="forbid")


class ConfigFlowerClient(BaseModel):
    """A Pydantic Model to validate the flower configuration given by the user.

    Attributes
    ----------
    server_address: str     = the server address and port
    ssl                     = the flower server ssl configuration
    one_tera                = grpc config ( 1 Tb = 1_073_741_824 b)
    grpc_max_message_length = grpc config ( 1 Tb = 1_073_741_824 b)
    alternate_client_class  = use an alternate subclass of FlowerClient 
    """

    PYBISCUS_CONFIG: ClassVar[str] = "flower_client"

    server_address:           str                        = "localhost:3333"
    ssl:                      Optional[ConfigSslClient]  = None
    # one_tera:                 str                        = "1 Tb = 1073741824 b"
    # grpc_max_message_length : Optional[int]              = None

    alternate_client_class:   Optional[ClientConfig()]   = None # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")


class ConfigClient(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    Attributes
    ----------
    pre_train_val: optional, default to False = states if at the beginning of a new fit round a validation loop will be performed, this allows to perform a validation loop on the validation dataset of the Client, after the client received the new, aggregated weights.
    root_dir: str      = the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    compute_context    = configuration of the client compute context
    model              = keywords for the LightningModule used
    data               = keywords for the LightningDataModule used.
    """

    PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus client configuration"

    root_dir: str           = "${oc.env:PWD}"
    flower_client:          ConfigFlowerClient
    client_run:             ConfigClientRun
    client_compute_context: ConfigClientComputeContext
    model:                  ModelConfig() # pyright: ignore[reportInvalidTypeForm]
    data:                   DataConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")
