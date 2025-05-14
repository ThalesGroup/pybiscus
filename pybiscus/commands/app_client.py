from pathlib import Path
from typing import Annotated

import flwr as fl
import torch
import typer
from pydantic import ValidationError

import pybiscus.core.pybiscus_logger as logm
from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclientfactory import FlowerFabricClientFactory
from pybiscus.plugin.registries import client_registry, datamodule_registry, model_registry
from pybiscus.flower_config.config_client import ConfigClient

from pybiscus.commands.apps_common import load_config
# from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclient import FlowerFabricClient

torch.backends.cudnn.enabled = True


def check_and_build_client_config(config: dict) -> ConfigClient:

    logm.console.log(config)
    _conf = ConfigClient(**config)
    logm.console.log(_conf)

    return _conf


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
    server_address: Annotated[
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
    server_address : str, optional
        the server address and port, by default None
    to_onnx : bool, optional
        if true, saves the final model into ONNX format. Only available now for Unet3D model! by default False

    Raises
    ------
    typer.Abort
        _description_
    ValidationError
        _description_
    """

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    # handling optional cid, rootdir and server address parameters
    # it overrides the values from configuration file

    if cid is not None:
        conf_loaded["cid"] = cid
    if root_dir is not None:
        conf_loaded["root_dir"] = root_dir
    if server_address is not None:
        conf_loaded["server_address"] = server_address
    try:
        _ = check_and_build_client_config(conf_loaded)
        logm.console.log("This is a valid config!")
    except ValidationError as e:
        logm.console.log("This is not a valid config!")
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
    server_address: Annotated[
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
    server_address: str, optional
        the server address and port
    """

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    # handling optional cid, rootdir and server address parameters
    # it overrides the values from configuration file

    if cid is not None:
        conf_loaded["client_run"]["cid"] = cid
    if root_dir is not None:
        conf_loaded["root_dir"] = root_dir
    if server_address is not None:
        conf_loaded["flower_client"]["server_address"] = server_address
    # logm.console.log(f"Conf specified: {dict(conf)}")

    conf = check_and_build_client_config(config=conf_loaded)

    # load the data management module from registry
    data_class = datamodule_registry()[conf.data.name]
    data = data_class(**conf.data.config.model_dump())

    data.setup(stage="fit")
    num_examples = {
        "trainset": len(data.train_dataloader()),
        "valset": len(data.val_dataloader()),
    }

    # load the model
    model_class = model_registry()[conf.model.name]
    model = model_class(**conf.model.config.model_dump())

    # load the client
    if conf.flower_client.alternate_client_class is None:
        client_factory = FlowerFabricClientFactory(conf,data,model,num_examples)
    else:
        client_factory = client_registry()[conf.flower_client.alternate_client_class.name](config,data,model,num_examples)
    client = client_factory.get_client()
    client.initialize()

    if conf.flower_client.ssl is None:
        ssl_secure_cnx=None
        ssl_root_certificate=None
    else:
        ssl_secure_cnx=conf.flower_client.ssl.secure_cnx
        ssl_root_certificate=conf.flower_client.ssl.root_certificate

    fl.client.start_client(
        server_address=conf.flower_client.server_address,
        client=client.to_client(),
        root_certificates=ssl_root_certificate,
        insecure= not ssl_secure_cnx,
    )

if __name__ == "__main__":
    app()
