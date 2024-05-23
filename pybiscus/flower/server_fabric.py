from pathlib import Path
from typing import Optional

import flwr as fl
import torch
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.console import console
from pybiscus.flower.callbacks import (
    better_aggregate,
    evaluate_config,
    fit_config,
    get_evaluate_fn,
    weighted_average_metrics,
)
from pybiscus.flower.client_fabric import ConfigFabric
from pybiscus.flower.strategies import ConfigFabricStrategy
from pybiscus.ml.data.cifar10.cifar10_datamodule import ConfigData_Cifar10
from pybiscus.ml.models.cnn.lit_cnn import ConfigModel_Cifar10
from pybiscus.ml.registry import datamodule_registry, model_registry


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
    weights_path: optional
        path to the weights of the model to be loaded at the beginning of the Federated Learning.

    """

    num_rounds: int = Field(gt=1)
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
    weights_path: Path = Field(default=None)

    model_config = ConfigDict(extra="forbid")


class Server:
    def __init__(
        self,
        root_dir: Path,
        # conf_logger: dict,
        logger: TensorBoardLogger,
        conf_strategy: ConfigStrategy,
        conf_fabric: ConfigFabric,
        conf_model: ConfigModel_Cifar10,
        conf_data: ConfigData_Cifar10,
        weights_path: Optional[Path],
    ):
        """Launch a Flower Server.

        This is a Typer command to launch a Flower Server, using the configuration given by config.
        Apart from the config parameter, other parameters are optional and, if given, override the associated parameter given by the parameter config.

        Parameters
        ----------
        config:
            path to a config file
        num_rounds: optional
            the number of Federated rounds
        server_adress: optional
            the IP adress and port of the Flower Server.
        weights_path: optional
            path to the weights of the model to be loaded at the beginning of the Federated Learning.

        Raises
        ------
        ValidationError
            the Pydantic error raised if the config is not validated.

        """
        conf_fabric = dict(conf_fabric)
        name_data = conf_data.name
        conf_data = dict(conf_data.config)
        name_model = conf_model.name
        conf_model = dict(conf_model.config)
        # name_strategy = conf_strategy.name
        conf_strategy = dict(conf_strategy.config)
        # conf_logger = dict(conf_logger)

        # self.logger = TensorBoardLogger(root_dir=root_dir + conf_logger["subdir"])
        self.logger = logger

        self.fabric = Fabric(**conf_fabric, loggers=self.logger)
        self.fabric.launch()
        model_class = model_registry[name_model]
        model = model_class(**conf_model)
        self.model = self.fabric.setup_module(model)
        data = datamodule_registry[name_data](**conf_data)
        data.setup(stage="test")
        _test_set = data.test_dataloader()
        self.test_set = self.fabric._setup_dataloader(_test_set)

        initial_parameters = None
        if weights_path is not None:
            state = self.fabric.load(weights_path)["model"]
            self.model.load_state_dict(state)

            params = torch.nn.ParameterList(
                [param.detach().numpy() for param in model.parameters()]
            )
            initial_parameters = fl.common.ndarrays_to_parameters(params)
            console.log(f"Loaded weights from {weights_path}")
        else:
            params = torch.nn.ParameterList(
                [param.detach().numpy() for param in model.parameters()]
            )
            initial_parameters = fl.common.ndarrays_to_parameters(params)

        self.strategy = fl.server.strategy.FedAvg(
            fit_metrics_aggregation_fn=better_aggregate(
                weighted_average_metrics,
                fabric=self.fabric,
                stage="fit",
                start_server_round=1,
            ),
            evaluate_metrics_aggregation_fn=better_aggregate(
                weighted_average_metrics,
                fabric=self.fabric,
                stage="val",
                start_server_round=1,
            ),
            evaluate_fn=get_evaluate_fn(
                testset=self.test_set, model=model, fabric=self.fabric
            ),
            on_fit_config_fn=fit_config,
            on_evaluate_config_fn=evaluate_config,
            initial_parameters=initial_parameters,
            **conf_strategy,
        )

    def launch(
        self,
        server_adress: str,
        num_rounds: int,
        client_configs: list[str],
        save_on_train_end: bool,
    ):
        fl.server.start_server(
            server_address=server_adress,
            config=fl.server.ServerConfig(num_rounds=num_rounds),
            strategy=self.strategy,
        )

        if save_on_train_end:
            state = {"model": self.model}
            self.fabric.save(self.fabric.logger.log_dir + "/checkpoint.pt", state)

        # with open(self.fabric.logger.log_dir + "/config_server_launch.yml", "w") as file:
        #     OmegaConf.save(config=conf, f=file)
        if client_configs is not None:
            for client_conf in client_configs:
                console.log(client_conf)
                _conf = OmegaConf.load(client_conf)
                with open(
                    self.fabric.logger.log_dir
                    + f"/config_client_{_conf['config_client']['cid']}_launch.yml",
                    "w",
                ) as file:
                    OmegaConf.save(config=_conf, f=file)
