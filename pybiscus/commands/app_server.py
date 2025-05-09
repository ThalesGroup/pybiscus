from pathlib import Path

import flwr as fl
import torch
import typer
from lightning.fabric import Fabric
from omegaconf import OmegaConf
from pydantic import ValidationError
from typing import Annotated

from pybiscus.core.pybiscus_logger import pluggable_logger as console
from pybiscus.plugin.registries import datamodule_registry, logger_registry, metricslogger_registry, model_registry, strategy_registry

from pybiscus.flower_config.config_server import ConfigServer

from pybiscus.commands.apps_common import load_config

#                    ------------------------------------------------

def check_and_build_server_config(conf_loaded: dict) -> ConfigServer :

    console.log(conf_loaded)
    _conf = ConfigServer(**conf_loaded)
    console.log(_conf)
        
    return _conf

#                    ------------------------------------------------

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")

########################################################################################"
########################################################################################"
########################################################################################"

@app.callback()
def server():
    """The server part of Pybiscus.

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
    server_listen_address: Annotated[
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
    server_listen_address : str, optional
        the server address and port, by default None
       
    Raises
    ------
    typer.Abort
        _description_
    typer.Abort
        _description_
    """

    conf_loaded = load_config(config)

    if num_rounds is not None:
        conf_loaded.server_run.num_rounds = num_rounds
    if server_listen_address is not None:
        conf_loaded.flower_server.listen_address = server_listen_address

    try:
        _ = check_and_build_server_config(conf_loaded=conf_loaded)
        console.log("This is a valid conf!")
    except ValidationError as e:
        console.log(f"This is not a valid config ! {e}")
        raise e

#                    ------------------------------------------------

def server_certificates(conf_ssl):

    certificates=None

    if conf_ssl is not None:
    
        root_certificate_path  = conf_ssl["root_certificate_path"]
        server_certificate_path= conf_ssl["server_certificate_path"]
        server_private_key_path= conf_ssl["server_private_key_path"]

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
    config:                Annotated[Path, typer.Argument()],
    num_rounds:            Annotated[int, typer.Option(rich_help_panel="Overriding some parameters")] = None,
    server_listen_address: Annotated[str, typer.Option(rich_help_panel="Overriding some parameters")] = None,
    weights_path:          Annotated[Path,typer.Option(rich_help_panel="Overriding some parameters")] = None,
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
    server_listen_address: optional
        the IP address and port of the Flower Server.
    weights_path: optional
        path to the weights of the model to be loaded at the beginning of the Federated Learning.
    """

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    # handling optional num rounds and server address parameters
    # it overrides the values from configuration file

    if num_rounds is not None:
        conf_loaded.server_run.num_rounds = num_rounds
    if server_listen_address is not None:
        conf_loaded.flower_server.listen_address = server_listen_address

    conf = check_and_build_server_config(conf_loaded)

    # load the logger
    _logger_class = logger_registry()[conf.server_run.logger.name]
    print(conf.server_run.logger.config)
    console = _logger_class(config=conf.server_run.logger.config).get_logger()

    # load the metricslogger
    _metricslogger_class = metricslogger_registry()[conf.server_compute_context.metrics_logger.name]
    _metricsloggerFactory = _metricslogger_class(conf.root_dir,conf.server_compute_context.metrics_logger.config)

    _metricsloggers = _metricsloggerFactory.get_loggers()

    fabric = Fabric(**conf.server_compute_context.hardware.model_dump(), loggers=_metricsloggers)
    fabric.launch()

    # load the model
    model_class = model_registry()[conf.model.name]
    _model = model_class(**conf.model.config.model_dump())

    model = fabric.setup_module(_model)

    # load the data management module from registry
    data_class = datamodule_registry()[conf.data.name]
    data = data_class(**conf.data.config.model_dump())
    
    data.setup(stage="test")
    test_set = fabric._setup_dataloader(data.test_dataloader())

    initial_parameters = None
    initial_parameters_log_message = "No weights provided, random server-side initialization instead."

    if weights_path is not None:
        state = fabric.load(weights_path)["model"]
        model.load_state_dict(state)
        initial_parameters_log_message = f"Loaded weights from {weights_path}"

    params = torch.nn.ParameterList(
        [param.detach().cpu().numpy() for param in model.parameters()]
    )
    initial_parameters = fl.common.ndarrays_to_parameters(params)
    console.log(initial_parameters_log_message)

    # NB : if the initial_parameters had been None
    # the behaviour would have been : Requesting initial parameters from one random client
    # Question: add this as a configuration option ?

    strategy = strategy_registry()[conf.strategy.name]( 
        model=model,
        fabric=fabric,
        testset=test_set,
        initial_parameters=initial_parameters,
        config=conf.strategy.config,
        
    ).get_strategy()

    console.log("start of flower server")

    # starting flower server
    fl.server.start_server(
        server_address = conf.flower_server.listen_address,
        config         = fl.server.ServerConfig(num_rounds=conf.server_run.num_rounds),
        strategy       = strategy,
        certificates   = server_certificates(conf.flower_server.ssl),
    )

    console.log("flower server ended")

    # optional checkpoint save
    if conf.server_run.save_on_train_end:
        state = {"model": model}
        fabric.save(fabric.logger.log_dir + "/checkpoint.pt", state)

    # server config logging
    with open(fabric.logger.log_dir + "/config_server_launch.yml", "w") as file:
        OmegaConf.save(config=conf_loaded, f=file)

    # optional clients config logging
    if conf.server_run.client_configs is not None:
        for client_conf in conf.server_run.client_configs:
            console.log(client_conf)
            _conf = OmegaConf.load(client_conf)
            with open(
                fabric.logger.log_dir + f"/config_client_{_conf.client_run.cid}_launch.yml", "w"
            ) as file:
                OmegaConf.save(config=_conf, f=file)



if __name__ == "__main__":
    app()
