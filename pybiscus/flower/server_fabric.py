from pydantic import BaseModel, ConfigDict, Field

from pybiscus.flower.client_fabric import ConfigFabric
from pybiscus.flower.strategies import ConfigFabricStrategy
from pybiscus.ml.data.cifar10.cifar10_datamodule import ConfigData_Cifar10
from pybiscus.ml.models.cnn.lit_cnn import ConfigModel_Cifar10


class ConfigStrategy(BaseModel):
    name: str
    config: ConfigFabricStrategy

    model_config = ConfigDict(extra="forbid")


class ConfigServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    num_rounds:
        the number of rounds for the FL session.
    server_adress:
        the server adress and port
    root_dir:
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    logger:
        a doctionnary holding the config for the logger.
    strategy:
        a dictionnary holding (partial) arguments for the needed Strategy
    fabric:
        a dictionnary holding all necessary keywords for the Fabric instance
    model:
        a dictionnary holding all necessary keywords for the LightningModule used
    data:
        a dictionnary holding all necessary keywords for the LightningDataModule used.
    clients_configs:
        a list of paths to the configuration files used by all clients.
    save_on_train_end: optional, default to False
        if true, the weights of the model are saved at the very end of the Federated Learning.
        The path is fabric.logger.log_dir + "/checkpoint.pt"
    """

    num_rounds: int
    server_adress: str
    root_dir: str
    logger: dict
    strategy: ConfigStrategy
    fabric: ConfigFabric
    model: ConfigModel_Cifar10
    data: ConfigData_Cifar10
    # model: Union[ConfigModel_Cifar10] = Field(discriminator="name")
    # data: Union[ConfigData_Cifar10] = Field(discriminator="name")
    client_configs: list[str] = Field(default=None)
    save_on_train_end: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid")
