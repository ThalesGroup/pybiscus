from enum import Enum
from typing import Optional, ClassVar
from typing_extensions import Annotated

import torch
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.flower_config.config_computecontext import ConfigClientComputeContext
from pybiscus.core.seed import Seed
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
    seed: int = seeds the client's random generators (order of the batches unless train.seed is set,
        dropout, augmentations) for a reproducible session; random if unset
    """

    PYBISCUS_CONFIG: ClassVar[str] = "client_run"

    cid: int            = Field(default=1, ge=0)
    pre_train_val: bool = Field(title="Validation before training", default=False, description='evaluate the global model received at each round before training on it (*_pre_train_val metrics)')
    optimizer_state: OptimizerState = OptimizerState.reset
    # new examples arriving between rounds: a data module reads them only in setup() otherwise, once
    refresh_data: bool = Field(default=False, description='read the data again before each round, to train on the examples arrived since (a data module may read only the new ones), or to evaluate them in a round without training (evaluateonly)')
    seed: Optional[Seed] = None

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
    # the webhooks' default address (logs, metrics, vignettes); in a session, set and locked by its manager
    manager_url:            str = Field(default="${oc.env:PYBISCUS_MANAGER_URL,http://localhost:5555}",
                                        description="address of the session manager, that the webhooks (logs, metrics, vignettes) default to")
    flower_client:          ConfigFlowerClient= Field(description='how the client reaches the Flower server')
    client_run:             ConfigClientRun= Field(description='identity and behaviour of the client during the session')
    client_compute_context: ConfigClientComputeContext= Field(description='hardware the client trains on')
    model:                  ModelConfig() # pyright: ignore[reportInvalidTypeForm]
    # Optional without a default: the form opens with a data section, only a relay unsets it
    data:                   Optional[DataConfig()] = Field(description="the client's data; none for a client that trains nothing (the relay of a hierarchical session)") # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")

    # the form leaves an unset Optional out: the after-validator, not Pydantic's "field required",
    # tells a client that trains from one that does not
    @model_validator(mode="before")
    @classmethod
    def data_left_out(cls, values):
        if isinstance(values, dict) and "data" not in values:
            values = {**values, "data": None}
        return values

    @model_validator(mode="after")
    def data_unless_nothing_trained(self):
        if self.data is None and client_needs_data(self.flower_client.alternate_client_class):
            raise ValueError("data is required: only a client that trains nothing (the relay of a hierarchical session) goes without")
        return self


def client_needs_data(alternate_client_class) -> bool:
    if alternate_client_class is None:
        return True
    from pybiscus.plugin.registries.client_registry import client_registry
    factory = client_registry().get(alternate_client_class.name)
    return getattr(factory, "NEEDS_DATA", True)
