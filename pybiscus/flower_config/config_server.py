from typing import Optional, ClassVar

from pydantic import BaseModel, ConfigDict

from pybiscus.flower_config.config_computecontext import ConfigServerComputeContext
from pybiscus.plugin.registries import LoggerConfig, ModelConfig, DataConfig, StrategyConfig, StrategyDecoratorConfig


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
    client_configs:    list[str] = []
    save_on_train_end: Optional[ConfigSaveWeights] = None
    loggers:           list[LoggerConfig()] # pyright: ignore[reportInvalidTypeForm]

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

    listen_address:     str = '[::]:3333'
    ssl:               Optional[ConfigSslServer] = None
    # one_tera: str = "1 Tb = 1073741824 b"
    # grpc_max_message_length : Optional[int] = None
    
    model_config = ConfigDict(extra="forbid")

# -----------------------------------------------

class ConfigServerStrategy(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_strategy"

    decorators:    list[StrategyDecoratorConfig()] # pyright: ignore[reportInvalidTypeForm]
    strategy:      StrategyConfig() # pyright: ignore[reportInvalidTypeForm]
    
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
    server_strategy:        ConfigServerStrategy
    data:                   DataConfig() # pyright: ignore[reportInvalidTypeForm]
    model:                  ModelConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")
