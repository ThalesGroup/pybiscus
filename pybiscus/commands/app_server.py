import flwr as fl
import torch
from jsonargparse import ActionConfigFile, ArgumentParser
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from omegaconf import OmegaConf
from rich.traceback import install

from pybiscus.console import console
from pybiscus.flower.callbacks import (
    better_aggregate,
    evaluate_config,
    fit_config,
    get_evaluate_fn,
    weighted_average_metrics,
)
from pybiscus.flower.server_fabric import ConfigServer
from pybiscus.ml.registry import datamodule_registry, model_registry

install()


def launch_server(
    config_server: ConfigServer,
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
    console.log(config_server)
    conf = dict(config_server)
    console.log(conf)
    conf_fabric = dict(config_server["fabric"])
    conf_data = dict(config_server["data"].config)
    conf_model = dict(config_server["model"].config)
    conf_strategy = dict(config_server["strategy"].config)

    logger = TensorBoardLogger(root_dir=conf["root_dir"] + conf["logger"]["subdir"])
    fabric = Fabric(**conf_fabric, loggers=logger)
    fabric.launch()
    model_class = model_registry[config_server["model"].name]
    model = model_class(**conf_model)
    model = fabric.setup_module(model)
    data = datamodule_registry[config_server["data"].name](**conf_data)
    data.setup(stage="test")
    _test_set = data.test_dataloader()
    test_set = fabric._setup_dataloader(_test_set)

    initial_parameters = None
    if config_server["weights_path"] is not None:
        state = fabric.load(config_server["weights_path"])["model"]
        model.load_state_dict(state)

        params = torch.nn.ParameterList(
            [param.detach().numpy() for param in model.parameters()]
        )
        initial_parameters = fl.common.ndarrays_to_parameters(params)
        console.log(f"Loaded weights from {config_server['weights_path']}")
    else:
        params = torch.nn.ParameterList(
            [param.detach().numpy() for param in model.parameters()]
        )
        initial_parameters = fl.common.ndarrays_to_parameters(params)

    strategy = fl.server.strategy.FedAvg(
        fit_metrics_aggregation_fn=better_aggregate(
            weighted_average_metrics, fabric=fabric, stage="fit", start_server_round=1
        ),
        evaluate_metrics_aggregation_fn=better_aggregate(
            weighted_average_metrics, fabric=fabric, stage="val", start_server_round=1
        ),
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
        OmegaConf.save(config=conf, f=file)
    if conf["client_configs"] is not None:
        for client_conf in conf["client_configs"]:
            console.log(client_conf)
            _conf = OmegaConf.load(client_conf)
            with open(
                fabric.logger.log_dir
                + f"/config_client_{_conf['config_client']['cid']}_launch.yml",
                "w",
            ) as file:
                OmegaConf.save(config=_conf, f=file)


def server_cli():
    parser = ArgumentParser(description="This is it!", parser_mode="omegaconf")
    parser.add_argument("--config_server", type=ConfigServer)

    parser.add_argument("--config", action=ActionConfigFile)

    cfg = parser.parse_args()
    console.log(cfg)
    launch_server(config_server=cfg["config_server"])


if __name__ == "__main__":
    server_cli()
