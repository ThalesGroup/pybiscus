from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import flwr as fl
import numpy as np
import torch
import typer
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.fabric.loggers import TensorBoardLogger
from omegaconf import OmegaConf
from typing_extensions import Annotated

from src.console import console
from src.ml.loops_fabric import test_loop
from src.flower.strategies import FabricStrategy
from src.ml.registry import datamodule_registry, model_registry


def set_params(model: torch.nn.ModuleList, params: List[np.ndarray]):
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
    testset,
    model,
    fabric,
) -> Callable[[fl.common.NDArrays], Optional[Tuple[float, float]]]:
    def evaluate(
        server_round: int, parameters: fl.common.NDArrays, config: Dict[str, Scalar]
    ) -> Optional[Tuple[float, float]]:
        set_params(model, parameters)

        loss, accuracy = test_loop(fabric=fabric, net=model, testloader=testset)
        return loss, {"Test loss": loss, "Test accuracy": accuracy}

    return evaluate


def weighted_average(metrics: List[Tuple[int, Metrics]]) -> Metrics:
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
    """The server part of Pybiscus.

    Launch the server!
    """


@app.command()
def launch_config(
    config: Annotated[Path, typer.Argument()],
    num_rounds: int = None,
    server_adress: str = None,
):
    """Launch a Flower Server.

    Args:
        num_rounds (int): number of rounds of FL
        server_adress (str): Flower server adress
    """
    if config is None:
        print("No config file")
        raise typer.Abort()
    if config.is_file():
        conf = OmegaConf.load(config)
        # console.log(conf)
    elif config.is_dir():
        print("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        print("The config doesn't exist")
        raise typer.Abort()

    if num_rounds is not None:
        conf["num_rounds"] = num_rounds
    if server_adress is not None:
        conf["server_adress"] = server_adress

    console.log(f"Conf specified: {dict(conf)}")

    logger = TensorBoardLogger(
        root_dir=conf["root_dir"] + conf["logger"]["subdir"]
    )
    fabric = Fabric(**conf["fabric"], loggers=logger)
    fabric.launch()
    _net = model_registry[conf["model"]["name"]](**conf["model"]["config"])
    net = fabric.setup_module(_net)
    data = datamodule_registry[conf["data"]["name"]](**conf["data"]["config"])
    data.setup(stage="test")
    _test_set = data.test_dataloader()
    test_set = fabric._setup_dataloader(_test_set)

    strategy = FabricStrategy(
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
        model=net,
        fabric=fabric,
        evaluate_fn=get_evaluate_fn(testset=test_set, model=net, fabric=fabric),
        on_fit_config_fn=fit_config,
        on_evaluate_config_fn=evaluate_config,
    )

    fl.server.start_server(
        server_address=conf["server_adress"],
        config=fl.server.ServerConfig(num_rounds=conf["num_rounds"]),
        strategy=strategy,
    )

    with open(fabric.logger.log_dir + "/config_server_launch.yml", "w") as file:
        OmegaConf.save(config=conf, f=file)
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
