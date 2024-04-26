from pathlib import Path
from typing import Annotated

import flwr as fl
import torch
import typer
from omegaconf import OmegaConf
from pydantic import ValidationError

from pybiscus.console import console
from pybiscus.flower.client_fabric import ConfigClient, FlowerClient
from pybiscus.ml.registry import datamodule_registry, model_registry

from . import change_conf_with_args

torch.backends.cudnn.enabled = True


def check_and_build_client_config(config: dict) -> tuple[dict, dict, dict]:
    _conf = ConfigClient(**config)
    console.log(_conf)
    conf = dict(_conf)
    conf_data = dict(conf["data"].config)
    conf_model = dict(conf["model"].config)
    return conf, conf_data, conf_model


app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")


@app.callback()
def client():
    """The client part of Pybiscus.

    It is made of two commands:

    * The command launch launches a client with a specified config file, to take part to a Federated Learning.
    * The command check checks if the provided configuration file satisfies the Pydantic constraints.
    """


@app.command(name="check")
def check_client_config(
    config: Annotated[Path, typer.Argument()],
    cid: Annotated[
        int, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    root_dir: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    server_adress: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
) -> None:
    """Check the provided client configuration file.

    The command loads the configuration file and checks the validity of the configuration using Pydantic.
    If the configuration is alright with respect to ConfigClient Pydantic BaseModel, nothing happens.
    Otherwise, raises the ValidationError by Pydantic -- which is quite verbose and should be useful understanding the issue with the configuration provided.

    You may pass optional parameters (in addition to the configuration file itself) to override the parameters given in the configuration.

    Parameters
    ----------
    config : Path
        the Path to the configuration file.
    cid: int, optional
        the client id
    root_dir: str, optional
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    server_adress: str, optional
        the server adress and port

    Raises
    ------
    ValidationError
        the Pydantic error raised if the config is not validated.
    """
    conf_loaded = OmegaConf.load(config)
    conf_merged = change_conf_with_args(
        config=conf_loaded, cid=cid, root_dir=root_dir, server_adress=server_adress
    )

    try:
        _ = check_and_build_client_config(conf_merged)
        console.log("This is a valid config!")
    except ValidationError as e:
        console.log("This is not a valid config!")
        raise e


@app.command(name="launch")
def launch_config(
    config: Annotated[Path, typer.Argument()],
    cid: Annotated[
        int, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    root_dir: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
    server_adress: Annotated[
        str, typer.Option(rich_help_panel="Overriding some parameters")
    ] = None,
) -> None:
    """Launch a FlowerClient.

    This is a Typer command to launch a Flower Client, using the configuration given by config.

    Parameters
    ----------
    config: Path
        path to a config file
    cid: int, optional
        the client id
    root_dir: str, optional
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    server_adress: str, optional
        the server adress and port

    Raises
    ------
    ValidationError
        the Pydantic error raised if the config is not validated.
    """

    conf_loaded = OmegaConf.load(config)
    conf_merged = change_conf_with_args(
        config=conf_loaded, cid=cid, root_dir=root_dir, server_adress=server_adress
    )

    conf, conf_data, conf_model = check_and_build_client_config(config=conf_merged)

    data = datamodule_registry[conf["data"].name](**conf_data)
    data.setup(stage="fit")
    num_examples = {
        "trainset": len(data.train_dataloader()),
        "valset": len(data.val_dataloader()),
    }

    model = model_registry[conf["model"].name](**conf_model)
    client = FlowerClient(
        cid=conf["cid"],
        model=model,
        data=data,
        num_examples=num_examples,
        conf_fabric=conf["fabric"],
        pre_train_val=conf["pre_train_val"],
    )
    client.initialize()
    client = client.to_client()
    fl.client.start_client(
        server_address=conf["server_adress"],
        client=client,
    )


if __name__ == "__main__":
    app()
