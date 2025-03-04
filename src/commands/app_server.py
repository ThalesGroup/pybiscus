from pathlib import Path

import flwr as fl
import torch
import typer
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from omegaconf import OmegaConf
from pydantic import ValidationError
from typing import Annotated

from src.console import console
from src.flower.strategies import FabricStrategy
from src.ml.registry import datamodule_registry, model_registry
from src.flower.server_fabric import (
    ConfigServer,
    weighted_average,
    fit_config,
    evaluate_config,
    get_evaluate_fn,
)

from src.commands.apps_common import load_config

#                    ------------------------------------------------

def check_and_build_server_config(conf_loaded: dict):
    console.log(conf_loaded)
    _conf = ConfigServer(**conf_loaded)
    console.log(_conf)
    conf          = dict(_conf)
    conf_fabric   = dict(conf["fabric"])
    conf_data     = dict(conf["data"].config)
    conf_model    = dict(conf["model"].config)
    conf_strategy = dict(conf["strategy"].config)
    conf_ssl      = None
    
    if "ssl" in conf and conf["ssl"] is not None:
        conf_ssl = dict(conf["ssl"]) 
        
    return conf, conf_fabric, conf_data, conf_model, conf_strategy, conf_ssl

#                    ------------------------------------------------

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")

########################################################################################"
########################################################################################"
########################################################################################"

@app.callback()
def server():
    """The server part of Pybiscus for Paroma.

    It is made of two commands:

    * The command launch launches a server for a Federated Learning, using the given config file.
    * The command check checks if the provided configuration file satisfies the Pydantic constraints.

    """

#                    ------------------------------------------------

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
    typer.Abort
        _description_
    typer.Abort
        _description_
    typer.Abort
        _description_
    ValidationError
        _description_
    """

    conf_loaded = load_config(config)

    if num_rounds is not None:
        conf_loaded["num_rounds"] = num_rounds
    if server_adress is not None:
        conf_loaded["server_adress"] = server_adress

    try:
        _ = check_and_build_server_config(conf_loaded=conf_loaded)
        console.log("This is a valid conf!")
    except ValidationError as e:
        console.log("This is not a valid config!")
        raise e

#                    ------------------------------------------------

def server_certificates(conf_ssl):

    certificates=None

    if conf_ssl is not None:
    
        root_certificate_path  =conf_ssl["root_certificate_path"]
        server_certificate_path=conf_ssl["server_certificate_path"]
        server_private_key_path=conf_ssl["server_private_key_path"]

        root_certificate   = None
        server_certificate = None
        server_private_key = None

        try:
            root_certificate = Path(root_certificate_path).read_bytes()
        except Exception as e:
            console.log(f"Can not read root_certificate from path {root_certificate_path} {e}")

        try:
            server_certificate = Path(server_certificate_path).read_bytes()
        except Exception as e:
            console.log(f"Can not read server_certificate from path {server_certificate_path} {e}")

        try:
            server_private_key = Path(server_private_key_path).read_bytes()
        except Exception as e:
            console.log(f"Can not read server_private_key from path {server_private_key_path} {e}")

        if root_certificate is not None and server_certificate is not None and server_private_key is not None:
            certificates = ( root_certificate, server_certificate, server_private_key )
        else:
            raise typer.Abort()

    return certificates

#                    ------------------------------------------------

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
    """

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    # handling optional num rounds and server address parameters
    # it overrides the values from configuration file

    if num_rounds is not None:
        conf_loaded["num_rounds"] = num_rounds
    if server_adress is not None:
        conf_loaded["server_adress"] = server_adress

    (
        conf,
        conf_fabric,
        conf_data,
        conf_model,
        conf_strategy,
        conf_ssl
    ) = check_and_build_server_config(conf_loaded=conf_loaded)

    logger = TensorBoardLogger(root_dir=conf["root_dir"] + conf["logger"]["subdir"])
    fabric = Fabric(**conf_fabric, loggers=logger)
    fabric.launch()

    # load the model
    model_class = model_registry[conf["model"].name]
    net = model_class(**conf_model)
    net = fabric.setup_module(net)

    # load the data management strategy from registry
    data = datamodule_registry[conf["data"].name](**conf_data)
    data.setup(stage="test")
    _test_set = data.test_dataloader()
    test_set = fabric._setup_dataloader(_test_set)

    initial_parameters = None
    if weights_path is not None:
        state = fabric.load(weights_path)["model"]
        model = model_class(**conf_model)
        model.load_state_dict(state)

        params = torch.nn.ParameterList(
            [param.detach().numpy() for param in model.parameters()]
        )
        initial_parameters = fl.common.ndarrays_to_parameters(params)
        console.log(f"Loaded weights from {weights_path}")

    strategy = FabricStrategy(
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
        model=net,
        fabric=fabric,
        evaluate_fn=get_evaluate_fn(testset=test_set, model=net, fabric=fabric),
        on_fit_config_fn=fit_config,
        on_evaluate_config_fn=evaluate_config,
        initial_parameters=initial_parameters,
        **conf_strategy,
    )

    # starting flower server
    fl.server.start_server(
        server_address = conf["server_adress"],
        config         = fl.server.ServerConfig(num_rounds=conf["num_rounds"]),
        strategy       = strategy,
        certificates   = server_certificates(conf_ssl),
    )

    # optional checkpoint save
    if conf["save_on_train_end"]:
        state = {"model": net}
        fabric.save(fabric.logger.log_dir + "/checkpoint.pt", state)

    # server config logging
    with open(fabric.logger.log_dir + "/config_server_launch.yml", "w") as file:
        OmegaConf.save(config=conf_loaded, f=file)

    # optional clients config logging
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

