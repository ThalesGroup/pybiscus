from collections import OrderedDict
from typing import Callable, Literal, Optional, Union, Dict, ClassVar

import flwr as fl
import numpy as np
import torch
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.pytorch import LightningModule
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.core.console import console
from pybiscus.flower.config_computecontext import ConfigServerComputeContext
from pybiscus.ml.loops_fabric import test_loop
from pybiscus.core.registries import ModelConfig, DataConfig, StrategyConfig


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

    file_path: str = "/final_checkpoint.pt"

    model_config = ConfigDict(extra="forbid")


class ConfigServerRun(BaseModel):
    """A Pydantic Model to validate the server run configuration given by the user.

    Attributes
    ----------
    num_rounds: int    = the number of rounds for the FL session.
    clients_configs    = list of paths to the configuration files used by all clients.
    save_on_train_end  = end of FL session model weights save flag
    """

    PYBISCUS_CONFIG: ClassVar[str] = "server_run"

    num_rounds:        int = 10
    client_configs:    list[str] = None
    save_on_train_end: Optional[ConfigSaveWeights] = None

    model_config = ConfigDict(extra="forbid")


class ConfigFlowerServer(BaseModel):
    """A Pydantic Model to validate the server run configuration given by the user.

    Attributes
    ----------
    server_listen_address = the server listen address and port
    ssl                   = the flower server ssl configuration
    """

    PYBISCUS_CONFIG: ClassVar[str] = "flower_server"

    listen_address:     str = '[::]:3333'
    ssl:               Optional[ConfigSslServer] = None

    model_config = ConfigDict(extra="forbid")


class ConfigServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    root_dir: str      = the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    logger: str        = the config for the logger.
    strategy           = arguments for the needed Strategy
    fabric             = keywords for the Fabric instance
    model              = keywords for the LightningModule used
    data               = keywords for the LightningDataModule used.
    """

    PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus server configuration"

    root_dir:               str = "${oc.env:PWD}"
    flower_server:          ConfigFlowerServer
    server_run:             ConfigServerRun
    server_compute_context: ConfigServerComputeContext
    strategy:               StrategyConfig() # pyright: ignore[reportInvalidTypeForm]
    data:                   DataConfig() # pyright: ignore[reportInvalidTypeForm]
    model:                  ModelConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")
