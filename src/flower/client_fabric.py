from collections import OrderedDict
from collections.abc import Mapping
from typing import Union, Optional
from typing_extensions import Annotated
from enum import Enum

import flwr as fl
import torch
from lightning.fabric import Fabric
from lightning.pytorch import LightningDataModule, LightningModule
from pydantic import BaseModel, ConfigDict, Field

from src.console import console
from src.ml.loops_fabric import test_loop, train_loop
from src.ml.registry import ModelConfig, DataConfig

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

    class Accelerator(str, Enum):
        cpu  = "cpu"
        gpu  = "gpu"
        auto = "auto"

    #accelerator: str = Field( default="auto", description="the type of accelerator to use: gpu, cpu, auto... See the Fabric documentation for more details.")
    accelerator: Accelerator = Field( default="auto", description="the type of accelerator to use: gpu, cpu, auto... See the Fabric documentation for more details.")

    devices: Union[int, list[int], str] = "auto"

ConfigModel = Annotated[int, lambda x: x > 0]

class ConfigSslClient(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    Attributes
    ----------
    secure_cnx: 
        Enables HTTPS connection when true, default value being false
        using system certificates if root_certificate is None

    root_certificate:
        he PEM-encoded root certificates path
    """

    secure_cnx: bool
    root_certificate: Optional[str] = None


class ConfigClient(BaseModel):
    """A Pydantic Model to validate the Client configuration given by the user.

    Attributes
    ----------
    cid: int
        client identifier
    pre_train_val: optional, default to False
        if true, at the beginning of a new fit round a validation loop will be performed.
        This allows to perform a validation loop on the validation dataset of the Client,
        after the client received the new, aggregated weights.
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
    ssl: dict
        a dictionnary holding all necessary options for https usage
    """

    cid: int
    pre_train_val: bool = Field(default=False)
    server_adress: str
    root_dir: str
    fabric: ConfigFabric
    model: ModelConfig
    data: DataConfig
    ssl: Optional[ConfigSslClient] = Field(default_factory=lambda: ConfigSslClient(secure_cnx=False))

    model_config = ConfigDict(extra="forbid")

def parse_optimizers(lightning_optimizers):
    """
    Parse the output of lightning configure_optimizers
    https://lightning.ai/docs/pytorch/stable/api/lightning.pytorch.core.LightningModule.html#lightning.pytorch.core.LightningModule.configure_optimizers
    To extract only the optimizers (and not the lr_schedulers)
    """
    optimizers = []
    if lightning_optimizers:
        if isinstance(lightning_optimizers, Mapping):
            optimizers.append(lightning_optimizers['optimizer']) 
        elif isinstance(lightning_optimizers, torch.optim.Optimizer):
            optimizers.append(lightning_optimizers)
        else:
            for optmizers_conf in lightning_optimizers:
                if isinstance(optmizers_conf, dict):
                    optimizers.append(lightning_optimizers)
                else:
                    optimizers.append(optmizers_conf)
    return optimizers


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
        pre_train_val: bool = False,
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
        self.pre_train_val = pre_train_val

        self.optimizers = parse_optimizers(self.model.configure_optimizers())

        self.fabric = Fabric(**self.conf_fabric)

    def initialize(self):
        self.fabric.launch()
        self.model, self.optimizers = self.fabric.setup(self.model, *self.optimizers)
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
        metrics = {}

        if self.pre_train_val:
            console.log(
                f"Round {config['server_round']}, pre train validation started..."
            )
            results_pre_train = test_loop(
                self.fabric, self.model, self._validation_dataloader
            )
            for key, val in results_pre_train.items():
                metrics[f"{key}_pre_train_val"] = val

        console.log(f"Round {config['server_round']}, training Started...")
        results_train = train_loop(
            self.fabric,
            self.model,
            self._train_dataloader,
            self.optimizers, # Alice TODO extend this to multiple optimizers ??
            epochs=config["local_epochs"],
        )
        console.log(f"Training Finished! Loss is {results_train['loss']}")
        metrics["cid"] = self.cid
        for key, val in results_train.items():
            metrics[key] = val
        return self.get_parameters(config={}), self.num_examples["trainset"], metrics

    def evaluate(self, parameters, config):
        console.log(f"[Client {self.cid}] evaluate, config: {config}")
        self.set_parameters(parameters)
        metrics = {}
        console.log(f"Round {config['server_round']}, evaluation Started...")
        results_evaluate = test_loop(
            self.fabric, self.model, self._validation_dataloader
        )
        console.log(
            f"Evaluation finished! Loss is {results_evaluate['loss']}, metric {list(results_evaluate.keys())[0]} is {results_evaluate[list(results_evaluate.keys())[0]]}"
        )
        metrics["cid"] = self.cid
        for key, val in results_evaluate.items():
            metrics[key] = val
        return results_evaluate["loss"], self.num_examples["valset"], metrics
