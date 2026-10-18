from pathlib import Path
from typing import Annotated

import flwr as fl
import torch
import typer
from omegaconf import OmegaConf
from pydantic import ValidationError

import pybiscus.core.gui_events as gui_events
import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclientfactory import FlowerFabricClientFactory
from pybiscus.flower.legacyentrypoints import hide_legacy_entry_point_warnings
from pybiscus.ml.datarefresh import WithdrawingClient, count_data
from pybiscus.plugin.registries.client_registry import client_registry
from pybiscus.plugin.registries.data_registry import datamodule_registry
from pybiscus.plugin.registries.model_registry import model_registry 
from pybiscus.flower_config.config_client import ConfigClient

from pybiscus.commands.apps_common import exit_on_invalid_config, load_config, apply_num_threads, apply_seed, resolve_defaults

torch.backends.cudnn.enabled = True


def apply_client_overrides(conf_loaded, cid, root_dir, server_address) -> None:

    # shared by check and launch: they used to diverge, check writing cid and
    # server_address at the root, where ConfigClient (extra="forbid") rejects them.
    # OmegaConf.update creates a missing section instead of raising ConfigKeyError,
    # leaving the diagnosis to Pydantic
    if cid is not None:
        OmegaConf.update(conf_loaded, "client_run.cid", cid)
    if root_dir is not None:
        OmegaConf.update(conf_loaded, "root_dir", root_dir)
    if server_address is not None:
        OmegaConf.update(conf_loaded, "flower_client.server_address", server_address)


def check_and_build_client_config(config: dict) -> ConfigClient:

    logm.console.log(config)
    _conf = resolve_defaults(ConfigClient, ConfigClient(**config))
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
    Otherwise, prints the ValidationError by Pydantic -- which is quite verbose and should be useful understanding the issue with the configuration provided -- and exits with code 65.

    You may pass optional parameters (in addition to the configuration file itself) to override the parameters given in the configuration.

    Parameters
    ----------
    config : Path
        the Path to the configuration file.
    cid : int, optional
        the client id, by default None
    root_dir : str, optional
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories, by default None
    server_address : str, optional
        the server address and port, by default None

    Raises
    ------
    typer.Abort
        _description_
    typer.Exit
        with code 65 if the configuration is not valid
    """

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    # handling optional cid, rootdir and server address parameters
    # it overrides the values from configuration file
    apply_client_overrides(conf_loaded, cid, root_dir, server_address)

    try:
        _ = check_and_build_client_config(conf_loaded)
    except ValidationError as e:
        exit_on_invalid_config(e)
    logm.console.log("This is a valid config!")


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
    apply_client_overrides(conf_loaded, cid, root_dir, server_address)
    # logm.console.log(f"Conf specified: {dict(conf)}")

    try:
        conf = check_and_build_client_config(config=conf_loaded)
    except ValidationError as e:
        exit_on_invalid_config(e)

    apply_num_threads(conf.client_compute_context.num_threads)
    apply_seed(conf.client_run.seed)

    if conf.flower_client.alternate_client_class is None:
        factory_class = FlowerFabricClientFactory
    else:
        factory_class = client_registry()[conf.flower_client.alternate_client_class.name]

    # a client that trains nothing (the relay of a hierarchical session) loads no data: its
    # machine may not hold the training set, and loading it cost a whole pass for nothing
    import pybiscus.core.pybiscuscontext as pcpc
    pcpc.pybiscus_context[pcpc.CID] = conf.client_run.cid

    if getattr(factory_class, "NEEDS_DATA", True):
        # load the data management module from registry
        data_class = datamodule_registry()[conf.data.name]
        data = data_class(**conf.data.config.model_dump())

        data.setup(stage="fit")
        # counted on the raw loaders: fabric.setup_dataloaders may swap in a DistributedSampler
        # that only sees this process' shard
        num_examples = count_data(data)
    else:
        data, num_examples = None, {"trainset": 0, "valset": 0}

    # load the model
    model_class = model_registry()[conf.model.name]
    model = model_class(**conf.model.config.model_dump())
    gui_events.set_main_metric(gui_events.main_metric_for_model(model))

    # expose client context
    pcpc.pybiscus_context[pcpc.MODEL] = model

    # load the client
    client_factory = factory_class(conf,data,model,num_examples)
    client = client_factory.get_client()
    client.initialize()

    if conf.flower_client.ssl is None:
        ssl_secure_cnx=None
        ssl_root_certificate=None
    else:
        ssl_secure_cnx=conf.flower_client.ssl.secure_cnx
        ssl_root_certificate=conf.flower_client.ssl.root_certificate

    hide_legacy_entry_point_warnings()
    fl.client.start_client(
        server_address=conf.flower_client.server_address,
        client=WithdrawingClient(client.to_client()),
        root_certificates=ssl_root_certificate,
        insecure= not ssl_secure_cnx,
    )

    # only on a normal end: the server disconnected its clients
    finalize = getattr(client, "finalize", None)
    if finalize is not None:
        finalize()

if __name__ == "__main__":
    app()
