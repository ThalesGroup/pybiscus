import flwr as fl
import torch
from jsonargparse import ActionConfigFile, ArgumentParser
from rich.traceback import install

from pybiscus.console import console
from pybiscus.flower.client_fabric import ConfigClient, FlowerClient
from pybiscus.ml.registry import datamodule_registry, model_registry

install()

torch.backends.cudnn.enabled = True


def launch_client(
    config_client: ConfigClient,
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
    # conf = dict(config_client)
    conf_data = dict(config_client["data"].config)
    conf_model = dict(config_client["model"].config)

    data = datamodule_registry[config_client["data"].name](**conf_data)
    data.setup(stage="fit")
    num_examples = {
        "trainset": len(data.train_dataloader()),
        "valset": len(data.val_dataloader()),
    }

    model = model_registry[config_client["model"].name](**conf_model)
    client = FlowerClient(
        cid=config_client["cid"],
        model=model,
        data=data,
        num_examples=num_examples,
        conf_fabric=config_client["fabric"],
        pre_train_val=config_client["pre_train_val"],
    )
    client.initialize()
    client = client.to_client()
    fl.client.start_client(
        server_address=config_client["server_adress"],
        client=client,
    )


def client_cli():
    parser = ArgumentParser(description="This is it!", parser_mode="omegaconf")
    parser.add_argument("--config_client", type=ConfigClient)

    parser.add_argument("--config", action=ActionConfigFile)

    cfg = parser.parse_args()
    console.log(cfg)
    launch_client(config_client=cfg["config_client"])


if __name__ == "__main__":
    client_cli()
