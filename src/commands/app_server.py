from pathlib import Path
from typing import Annotated

import flwr as fl
import torch
import typer
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from omegaconf import OmegaConf
from pydantic import ValidationError

from src.console import console
from src.flower.server_fabric import (
    ConfigServer,
    evaluate_config,
    fit_config,
    get_evaluate_fn,
    weighted_average,
)
from src.flower.strategies import FabricStrategy
from src.ml.registry import datamodule_registry, model_registry

from . import change_conf_with_args


def check_and_build_server_config(conf_loaded: dict):
    console.log(conf_loaded)
    _conf = ConfigServer(**conf_loaded)
    console.log(_conf)
    conf = dict(_conf)
    conf_fabric = dict(conf["fabric"])
    conf_data = dict(conf["data"].config)
    conf_model = dict(conf["model"].config)
    conf_strategy = dict(conf["strategy"].config)
    return conf, conf_fabric, conf_data, conf_model, conf_strategy


app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")


@app.callback()
def server():
    """The server part of Pybiscus for Paroma.

    It is made of two commands:

    * The command launch launches a server for a Federated Learning, using the given config file.
    * The command check checks if the provided configuration file satisfies the Pydantic constraints.

    """


@app.command(name="check")
def check_server_config(
    config: Annotated[Path, typer.Argument()],
    num_rounds: Annotated[
        int, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    server_adress: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
) -> None:
    """Check the provided server configuration file.

    The command loads the configuration file and checks the validity of the configuration using Pydantic.
    If the configuration is alright with respect to ConfigServer Pydantic BaseModel, nothing happens.
    Otherwise, raises the ValidationError by Pydantic -- which is quite verbose and should be useful understanding the issue with the configuration provided.

    You may pass optional parameters (in addition to the configuration file itself) to override the parameters given in the configuration.

    Parameters
    ----------
    config : Path
        the Path to the configuration file.
    num_rounds : int, optional
        the number of round of Federated Learning, by default None
    server_adress : str, optional
        the server adress and port, by default None

    Raises
    ------
    ValidationError
        the Pydantic error raised if the config is not validated.
    """
    conf_loaded = OmegaConf.load(config)
    conf_merged = change_conf_with_args(
        config=conf_loaded, num_rounds=num_rounds, server_adress=server_adress
    )

    try:
        _ = check_and_build_server_config(conf_loaded=conf_merged)
        console.log("This is a valid conf!")
    except ValidationError as e:
        console.log("This is not a valid config!")
        raise e


@app.command(name="launch")
def launch_config(
    config: Annotated[Path, typer.Argument()],
    num_rounds: Annotated[
        int, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    server_adress: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    weights_path: Annotated[
        Path,
        typer.Option(
            rich_help_panel="Overriding some parameters",
        ),
    ] = None,
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
    conf_loaded = OmegaConf.load(config)
    conf_merged = change_conf_with_args(
        config=conf_loaded, num_rounds=num_rounds, server_adress=server_adress
    )

    (
        conf,
        conf_fabric,
        conf_data,
        conf_model,
        conf_strategy,
    ) = check_and_build_server_config(conf_loaded=conf_merged)

    logger = TensorBoardLogger(root_dir=conf["root_dir"] + conf["logger"]["subdir"])
    fabric = Fabric(**conf_fabric, loggers=logger)
    fabric.launch()
    model_class = model_registry[conf["model"].name]
    model = model_class(**conf_model)
    model = fabric.setup_module(model)
    data = datamodule_registry[conf["data"].name](**conf_data)
    data.setup(stage="test")
    _test_set = data.test_dataloader()
    test_set = fabric._setup_dataloader(_test_set)

    initial_parameters = None
    if weights_path is not None:
        state = fabric.load(weights_path)["model"]
        model.load_state_dict(state)

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

    strategy = FabricStrategy(
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
        # evaluate_metrics_aggregation_fn=better_aggregate(weighted_average_metrics),
        model=model,
        fabric=fabric,
        evaluate_fn=get_evaluate_fn(testset=test_set, model=model, fabric=fabric),
        on_fit_config_fn=fit_config,
        on_evaluate_config_fn=evaluate_config,
        initial_parameters=initial_parameters,
        **conf_strategy,
    )

    fl.server.start_server(
        server_address=conf["server_adress"],
        config=fl.server.ServerConfig(num_rounds=conf["num_rounds"]),
        strategy=strategy,
    )

    if conf["save_on_train_end"]:
        state = {"model": model}
        fabric.save(fabric.logger.log_dir + "/checkpoint.pt", state)

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
