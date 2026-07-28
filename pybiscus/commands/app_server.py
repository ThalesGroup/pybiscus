from pathlib import Path
import os
import flwr as fl
import torch
import typer
from lightning.fabric import Fabric
from omegaconf import OmegaConf
from pydantic import ValidationError
from typing import Annotated

from pybiscus.core.ensure_filesystem import ensure_dir_exists, ensure_file_dir_exists
from pybiscus.core.logger.filelogger.filelogger import FileLoggerFactory
from pybiscus.core.logger.richlogger.richloggerfactory import RichLoggerFactory
from pybiscus.core.metricslogger.file.filemetricslogger import FileMetricsLoggerFactory
import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.logger.multiplelogger.multipleloggerfactory import MultipleLoggerFactory
from pybiscus.core.metricslogger.multiplemetricslogger.multiplemetricsloggerfactory import MultipleMetricsLoggerFactory
from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.commands.onnx_mngt import to_onnx_with_datamodule
from pybiscus.commands.apps_common import load_config
from pybiscus.plugin.registries.data_registry import datamodule_registry
from pybiscus.plugin.registries.logger_registry import logger_registry
from pybiscus.plugin.registries.metriclogger_registry import metricslogger_registry
from pybiscus.plugin.registries.model_registry import model_registry
from pybiscus.plugin.registries.strategy_registry import strategy_registry
from pybiscus.plugin.registries.strategydecorator_registry import strategydecorator_registry


#                    ------------------------------------------------

def check_and_build_server_config(conf_loaded: dict) -> ConfigServer :

    logm.console.log(conf_loaded)
    _conf = ConfigServer(**conf_loaded)
    logm.console.log(_conf)
        
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
        logm.console.log("This is a valid conf!")
    except ValidationError as e:
        logm.console.log(f"This is not a valid config ! {e}")
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
            logm.console.log(f"Can not read root_certificate from path {root_certificate_path} {e}")

        try:
            server_certificate = Path(server_certificate_path).read_bytes()
        except Exception as e:
            logm.console.log(f"Can not read server_certificate from path {server_certificate_path} {e}")

        try:
            server_private_key = Path(server_private_key_path).read_bytes()
        except Exception as e:
            logm.console.log(f"Can not read server_private_key from path {server_private_key_path} {e}")

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

    # compute the reporting path
    
    if conf.server_run.reporting:

        reporting_path = Path(conf.server_run.reporting.basedir)

        if conf.server_run.reporting.add_timestamp_in_path:
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            reporting_path = reporting_path / timestamp

            # path symbolic link to "current"
            current_link = Path(conf.server_run.reporting.basedir) / "current"

            # remove existing one
            if current_link.is_symlink() or current_link.exists():
                current_link.unlink()

            # a relative symlink is computed
            relative_target = os.path.relpath(reporting_path, start=current_link.parent)

            # create the new symbolic link
            os.symlink(relative_target, current_link)

    else:
        reporting_path = Path(conf.root_dir)

    ensure_dir_exists(reporting_path)

    logm.console.log(f"reporting 💾 path is set to : {reporting_path}")

    # load the loggers
    _logger_classes = [ logger_registry()[logger.name](config=logger.config) for logger in conf.server_run.loggers ]

    # additional factory for logging into reporting directory
    _file_logger_factory = FileLoggerFactory( reporting_path / Path("server_logs.txt") )

    if len(_logger_classes) > 0:
        # add this factory to the list
        _logger_classes.append( _file_logger_factory )
    else:
        # default is : log to the console and to reporting directory
        _logger_classes = [ RichLoggerFactory(), _file_logger_factory ]

    logm.console = MultipleLoggerFactory(_logger_classes).get_logger()

    # load the metricsloggers
    _metricslogger_classes = [ metricslogger_registry()[mlogger.name](config=mlogger.config) for mlogger in conf.server_compute_context.metrics_loggers ]

    # additional factory for logging metrics into reporting directory
    _file_metrics_logger_factory = FileMetricsLoggerFactory( "metrics.txt" )

    # add this factory to the list
    _metricslogger_classes.append( _file_metrics_logger_factory )

    _metricslogger = MultipleMetricsLoggerFactory(_metricslogger_classes).get_metricslogger(reporting_path)

    fabric = Fabric(**conf.server_compute_context.hardware.model_dump(), loggers=[_metricslogger])
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
        [param.detach().cpu().numpy() for _, param in model.state_dict().items()]
    )
    initial_parameters = fl.common.ndarrays_to_parameters(params)
    logm.console.log(initial_parameters_log_message)

    # NB : if the initial_parameters had been None
    # the behaviour would have been : Requesting initial parameters from one random client
    # Question: add this as a configuration option ?

    pybiscus_strategy = strategy_registry()[conf.server_strategy.strategy.name]( 
        model=model,
        fabric=fabric,
        testset=test_set,
        initial_parameters=initial_parameters,
        config=conf.server_strategy.strategy.config,
    )
    strategy = pybiscus_strategy.get_strategy( conf.server_run.clients_fit_local_epochs )

    logm.console.log(f"setting 🛠️ strategy <{conf.server_strategy.strategy.name}>")

    # expose server context
    import pybiscus.core.pybiscuscontext as pcpc
    pcpc.pybiscus_context["reporting_path"] = Path(reporting_path)
    pcpc.pybiscus_context["model"] = model
    pcpc.pybiscus_context["fabric"] = fabric

    # chaining strategy decorators 
    for conf_decorator in conf.server_strategy.pipeline:
        logm.console.log(f"setting 🛠️🎀 strategy decorator <{conf_decorator.name}>")
        decorator_class = strategydecorator_registry()[conf_decorator.name]
        strategy = decorator_class(strategy,pybiscus_strategy,conf_decorator.config )
    
    logm.console.log("start of 🌺🖥️ flower server")

    # starting flower server
    fl.server.start_server(
        server_address = conf.flower_server.listen_address,
        config         = fl.server.ServerConfig(num_rounds=conf.server_run.num_rounds),
        strategy       = strategy,
        certificates   = server_certificates(conf.flower_server.ssl),
    )

    logm.console.log("🌺🖥️ flower server ended")

    # produce reporting
    if conf.server_run.reporting:

        # optional checkpoint save
        if conf.server_run.reporting.save_on_train_end:

            checkpoint_path = reporting_path / conf.server_run.reporting.save_on_train_end.filename

            state = {"model": model}

            ensure_file_dir_exists(checkpoint_path)
            fabric.save(checkpoint_path, state)
            logm.console.log(f"[fabric] save checkpoint 💾📍🗄️to : {checkpoint_path}")

        # optional onnx export
        if conf.server_run.reporting.onnx_export:
            onnx_path = reporting_path / conf.server_run.reporting.onnx_export.filename
            ensure_file_dir_exists(onnx_path)
            to_onnx_with_datamodule( model, data, onnx_path, conf.server_run.reporting.onnx_export)

            if conf.server_run.reporting.onnx_export.post_validation:
                # validate_onnx_export(onnx_path: str, model, input_sample: torch.Tensor)
                pass

        # server config logging
        serverconfig_path = reporting_path / conf.server_run.reporting.server_config_filename
        ensure_file_dir_exists(serverconfig_path)
        with open(serverconfig_path, "w") as file:
            OmegaConf.save(config=conf_loaded, f=file)
            logm.console.log(f"[pybiscus] save server config 💾🖧⚙️ to : {serverconfig_path}")


    # optional clients config logging
    # manage statically clients config (path defined in server config: legacy CLI mode)
    if conf.server_run.client_configs is not None:
        for client_conf in conf.server_run.client_configs:
            logm.console.log(client_conf)
            _conf = OmegaConf.load(client_conf)

            clientconfig_path = reporting_path / f"/config_client_{_conf.client_run.cid}_launch.yml"
            ensure_file_dir_exists(clientconfig_path)
            with open(clientconfig_path, "w") as file:
                OmegaConf.save(config=_conf, f=file)

    # manage dynamically clients config (agent mode )
    # HTTP POSTed files are stored in ./experiments/config_clients/client_name.yml
    import shutil

    # clients config directory is moved from well-known path 
    # (as the server agent does not use its yaml conf file)
    # into reporting_path
    # from pathlib import Path

    clients_config_dir = Path("./experiments/config_clients")

    if clients_config_dir.exists() and clients_config_dir.is_dir():
        logm.console.log(f"[pybiscus] save clients config 💾🖥️⚙️ as : {reporting_path / "config_clients"}")
        shutil.move(clients_config_dir, reporting_path)

if __name__ == "__main__":
    app()
