from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Callable, Optional

import flwr as fl
import numpy as np
import torch
import typer
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from lightning.pytorch import LightningModule
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict

from src.console import console
from src.flower.client_fabric import ConfigFabric
from src.flower.strategies import ConfigFabricStrategy, FabricStrategy
from src.ml.data.cifar10.cifar10_datamodule import ConfigData_Cifar10
from src.ml.loops_fabric import test_loop
from src.ml.models.cnn.lit_cnn import ConfigModel_Cifar10
from src.ml.registry import datamodule_registry, model_registry


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
    client_configs: list[str] = None

    model_config = ConfigDict(extra="forbid")


def set_params(model: torch.nn.ModuleList, params: list[np.ndarray]):
    params_dict = zip(model.state_dict().keys(), params)
    state_dict = OrderedDict({k: torch.from_numpy(np.copy(v)) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)


def fit_config(server_round: int):
    """Return training configuration dict for each round."""
    config = {
        "server_round": server_round,  # The current round of federated learning
        "local_epochs": 1,  # if server_round < 2 else 2,  #
    }
    return config


def evaluate_config(server_round: int):
    """Return training configuration dict for each round."""
    config = {
        "server_round": server_round,  # The current round of federated learning
        # "local_epochs": 1,  # if server_round < 2 else 2,  #
    }
    return config


def get_evaluate_fn(
    testset: torch.utils.data.DataLoader,
    model: LightningModule,
    fabric: Fabric,
) -> Callable[[fl.common.NDArrays], Optional[tuple[float, float]]]:
    def evaluate(
        server_round: int, parameters: fl.common.NDArrays, config: dict[str, Scalar]
    ) -> Optional[tuple[float, float]]:
        set_params(model, parameters)

        loss, accuracy = test_loop(fabric=fabric, net=model, testloader=testset)
        return loss, {"Test loss": loss, "Test accuracy": accuracy}

    return evaluate


def weighted_average(metrics: list[tuple[int, Metrics]]) -> Metrics:
    losses = [num_examples * m["loss"] for num_examples, m in metrics]
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]
    output = {
        "accuracy": sum(accuracies) / sum(examples),
        "loss": sum(losses) / sum(examples),
    }
    console.log(f"Averaged metrics: {output}")
    return output


app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="markdown")


@app.callback()
def server():
    """

    **The server part of Pybiscus.**

    ---

    The command launch-config launches a server for a Federated Learning, using the given config file.
    """


@app.command()
def launch_config(
    config: Annotated[Path, typer.Argument()],
    num_rounds: int = None,
    server_adress: str = None,
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
    """
    if config is None:
        print("No config file")
        raise typer.Abort()
    if config.is_file():
        conf_loaded = OmegaConf.load(config)
        # console.log(conf)
    elif config.is_dir():
        print("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        print("The config doesn't exist")
        raise typer.Abort()

    if num_rounds is not None:
        conf_loaded["num_rounds"] = num_rounds
    if server_adress is not None:
        conf_loaded["server_adress"] = server_adress

    _conf = ConfigServer(**conf_loaded)
    console.log(_conf)
    conf = dict(_conf)
    conf_fabric = dict(conf["fabric"])
    conf_data = dict(conf["data"].config)
    conf_model = dict(conf["model"].config)
    conf_strategy = dict(conf["strategy"].config)

    logger = TensorBoardLogger(root_dir=conf["root_dir"] + conf["logger"]["subdir"])
    fabric = Fabric(**conf_fabric, loggers=logger)
    fabric.launch()
    _net = model_registry[conf["model"].name](**conf_model)
    net = fabric.setup_module(_net)
    data = datamodule_registry[conf["data"].name](**conf_data)
    data.setup(stage="test")
    _test_set = data.test_dataloader()
    test_set = fabric._setup_dataloader(_test_set)

    strategy = FabricStrategy(
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
        model=net,
        fabric=fabric,
        evaluate_fn=get_evaluate_fn(testset=test_set, model=net, fabric=fabric),
        on_fit_config_fn=fit_config,
        on_evaluate_config_fn=evaluate_config,
        **conf_strategy,
    )

    fl.server.start_server(
        server_address=conf["server_adress"],
        config=fl.server.ServerConfig(num_rounds=conf["num_rounds"]),
        strategy=strategy,
    )

    with open(fabric.logger.log_dir + "/config_server_launch.yml", "w") as file:
        OmegaConf.save(config=conf_loaded, f=file)
    if conf["client_configs"] is not None:
        for client_conf in conf["client_configs"]:
            console.log(client_conf)
            _conf = OmegaConf.load(client_conf)
            with open(
                fabric.logger.log_dir + f"/config_client_{_conf['cid']}_launch.yml", "w"
            ) as file:
                OmegaConf.save(config=_conf, f=file)


if __name__ == "__main__":
    app()
