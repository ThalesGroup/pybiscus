from collections import OrderedDict
import flwr as fl
from lightning import Fabric, LightningDataModule, LightningModule
import torch

from pybiscus.flower.config_client import parse_optimizers
from pybiscus.flower.config_computecontext import ConfigClientComputeContext
from pybiscus.ml.loops_fabric import test_loop, train_loop
from pybiscus.core.pybiscus_logger import pluggable_logger as console

class FlowerFabricClient(fl.client.NumPyClient):
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
        conf_fabric: ConfigClientComputeContext,
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
        conf_fabric : ConfigClientComputeContext
            a Pydantic-validated configuration for the Fabric instance
        """
        super().__init__()
        self.cid = cid
        self.model = model
        self.data = data

        self.conf_fabric = conf_fabric.model_dump()
        self.num_examples = num_examples
        self.pre_train_val = pre_train_val

        self.optimizers = parse_optimizers(self.model.configure_optimizers())

        self.fabric = Fabric(**self.conf_fabric)

    def initialize(self):
        self.fabric.launch()

        if hasattr(self, "optimizers") and self.optimizers:
            self.model, *self.optimizers = self.fabric.setup(self.model, *self.optimizers)
        else:
            self.model = self.fabric.setup(self.model)

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
