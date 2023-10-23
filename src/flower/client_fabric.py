from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Union

import flwr as fl
import torch
import typer
from lightning.fabric import Fabric
from lightning.pytorch import LightningDataModule, LightningModule
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict

from src.console import console
from src.ml.data.cifar10.cifar10_datamodule import ConfigData_Cifar10
from src.ml.loops_fabric import test_loop, train_loop
from src.ml.models.cnn.lit_cnn import ConfigModel_Cifar10
from src.ml.registry import datamodule_registry, model_registry

torch.backends.cudnn.enabled = True


class ConfigFabric(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    This is a (partial) reproduction of the Fabric API found here:
    https://lightning.ai/docs/fabric/stable/api/generated/lightning.fabric.fabric.Fabric.html#lightning.fabric.fabric.Fabric

    Attributes
    ----------
    accelerator:
        the type of accelerator to use: gpu, cpu, auto... See the Fabric documentation for more details.
    devices: optional
        either an integer (the number of devices needed); a list of integers (the id of the devices); or
        the string "auto" to let Fabric choose the best option available.
    """

    accelerator: str
    devices: Union[int, list[int], str] = "auto"


class ConfigClient(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    Attributes
    ----------
    cid: int
        client identifier
    server_adress: str
        the server adress and port
    root_dir: str
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    fabric: dict
        a dictionnary holding all necessary keywords for the Fabric instance
    model: dict
        a dictionnary holding all necessary keywords for the LightningModule used
    data: dict
        a dictionnary holding all necessary keywords for the LightningDataModule used.
    """

    cid: int
    server_adress: str
    root_dir: str
    fabric: ConfigFabric
    model: ConfigModel_Cifar10
    data: ConfigData_Cifar10
    # model: Union[ConfigModel_Cifar10, ...] = Field(discriminator="name")
    # data: Union[ConfigData_Cifar10, ...] = Field(discriminator="name")

    model_config = ConfigDict(extra="forbid")


class FlowerClient(fl.client.NumPyClient):
    """A Fabric-based, modular Flower Client.

    The present FlowerClient override the usual Flower Client, by using Fabric as a backbone.
    The Client now holds data, the model and a Fabric instance which takes care of everything regarding
    hardware, precision and such.

    """

    def __init__(
        self,
        cid: int,
        model: LightningModule,
        data: LightningDataModule,
        num_examples: dict[str, int],
        conf_fabric: ConfigFabric,
    ) -> None:
        """Initialize the FlowerClient instance.

        Override the usual fl.client.NumPyClient configuration and add data, model and fabric attributes.

        Parameters
        ----------
        cid : int
            the client identifier
        model : LightningModule
            the model used for the FL training
        data : LightningDataModule
            the data used for the training/validation process
        num_examples : dict[str, int]
            needed by Flower, for the FedAvg Streategy typically
        conf_fabric : ConfigFabric
            a Pydantic-validated configuration for the Fabric instance
        """
        super().__init__()
        self.cid = cid
        self.model = model
        self.data = data

        self.conf_fabric = dict(conf_fabric)
        self.num_examples = num_examples

        self.optimizer = self.model.configure_optimizers()

        self.fabric = Fabric(**self.conf_fabric)

    def initialize(self):
        self.fabric.launch()
        self._model, self._optimizer = self.fabric.setup(self.model, self.optimizer)
        (
            self._train_dataloader,
            self._validation_dataloader,
        ) = self.fabric.setup_dataloaders(
            self.data.train_dataloader(), self.data.val_dataloader()
        )

    def get_parameters(self, config):
        console.log(f"[Client] get_parameters, config: {config}")
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        console.log("[Client] set_parameters")
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        console.log(f"[Client {self.cid}] fit, config: {config}")
        self.set_parameters(parameters)
        console.log(f"Round {config['server_round']}, training Started...")
        loss, accuracy = train_loop(
            self.fabric,
            self._model,
            self._train_dataloader,
            self._optimizer,
            epochs=config["local_epochs"],
        )
        console.log(f"Training Finished! Loss is {loss}")
        metrics = {"accuracy": accuracy, "loss": loss, "cid": self.cid}
        return self.get_parameters(config={}), self.num_examples["trainset"], metrics

    def evaluate(self, parameters, config):
        console.log(f"[Client {self.cid}] evaluate, config: {config}")
        self.set_parameters(parameters)
        console.log(f"Round {config['server_round']}, evaluation Started...")
        loss, accuracy = test_loop(
            self.fabric, self._model, self._validation_dataloader
        )
        console.log(f"Evaluation finished! Loss is {loss}, accuracy is {accuracy}")
        metrics = {"accuracy": accuracy, "loss": loss, "cid": self.cid}
        return loss, self.num_examples["valset"], metrics


app = typer.Typer(pretty_exceptions_show_locals=False)


@app.callback()
def client():
    """

    **The client part of Pybiscus!**

    ---

    The command launch-config launches a client with a specified config file, to take part to a Federated Learning.
    """


@app.command()
def launch_config(
    config: Annotated[Path, typer.Argument()],
    cid: int = None,
    root_dir: str = None,
    server_adress: str = None,
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
    """

    if config is None:
        print("No config file")
        raise typer.Abort()
    if config.is_file():
        conf_loaded = OmegaConf.load(config)
    elif config.is_dir():
        print("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        print("The config doesn't exist")
        raise typer.Abort()

    if cid is not None:
        conf_loaded["cid"] = cid
    if root_dir is not None:
        conf_loaded["root_dir"] = root_dir
    if server_adress is not None:
        conf_loaded["server_adress"] = server_adress
    # console.log(f"Conf specified: {dict(conf)}")

    _conf = ConfigClient(**conf_loaded)
    console.log(_conf)
    conf = dict(_conf)
    conf_data = dict(conf["data"].config)
    conf_model = dict(conf["model"].config)

    data = datamodule_registry[conf["data"].name](**conf_data)
    data.setup(stage="fit")
    num_examples = {
        "trainset": len(data.train_dataloader()),
        "valset": len(data.val_dataloader()),
    }

    net = model_registry[conf["model"].name](**conf_model)
    client = FlowerClient(
        cid=conf["cid"],
        model=net,
        data=data,
        num_examples=num_examples,
        conf_fabric=conf["fabric"],
    )
    client.initialize()
    fl.client.start_numpy_client(
        server_address=conf["server_adress"],
        client=client,
    )


if __name__ == "__main__":
    app()
