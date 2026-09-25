from collections import OrderedDict
from collections.abc import Mapping
import flwr as fl
from lightning import Fabric, LightningDataModule, LightningModule
import torch

from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.flower_config.config_computecontext import ConfigClientComputeContext
from pybiscus.ml.loops_fabric import SchedulerConfig, check_schedulers_monitor, test_loop, train_loop
import pybiscus.core.pybiscus_logger as logm


def _scheduler_config(entry, monitor=None) -> SchedulerConfig:
    if not isinstance(entry, Mapping):
        return SchedulerConfig(entry, monitor=monitor)
    interval = entry.get("interval", "epoch")
    if interval not in ("epoch", "step"):
        raise PybiscusValueException(f"lr_scheduler interval must be 'epoch' or 'step', got '{interval}'")
    return SchedulerConfig(
        entry["scheduler"],
        interval=interval,
        frequency=entry.get("frequency", 1),
        monitor=entry.get("monitor", monitor),
    )


def _parse_optimizer_dict(conf: Mapping):
    scheduler = conf.get("lr_scheduler")
    schedulers = [] if scheduler is None else [_scheduler_config(scheduler, conf.get("monitor"))]
    return [conf["optimizer"]], schedulers


# every return form of configure_optimizers documented by Lightning must be accepted, plugins are
# written as plain Lightning modules:
# https://lightning.ai/docs/pytorch/stable/api/lightning.pytorch.core.LightningModule.html#lightning.pytorch.core.LightningModule.configure_optimizers
def parse_optimizers(lightning_optimizers):
    conf = lightning_optimizers
    if conf is None:
        return [], []
    if isinstance(conf, torch.optim.Optimizer):
        return [conf], []
    if isinstance(conf, Mapping):
        return _parse_optimizer_dict(conf)
    if isinstance(conf, (list, tuple)):
        if len(conf) == 2 and all(isinstance(part, (list, tuple)) for part in conf):
            optimizers, schedulers = conf
            return list(optimizers), [_scheduler_config(s) for s in schedulers]
        if all(isinstance(part, Mapping) for part in conf):
            optimizers, schedulers = [], []
            for part in conf:
                part_optimizers, part_schedulers = _parse_optimizer_dict(part)
                optimizers += part_optimizers
                schedulers += part_schedulers
            return optimizers, schedulers
        if all(isinstance(part, torch.optim.Optimizer) for part in conf):
            return list(conf), []
    raise PybiscusValueException(f"unsupported configure_optimizers() return value: {conf!r}")

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
        conf_fabric: dict,
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

        self.optimizers, self.schedulers = parse_optimizers(self.model.configure_optimizers())
        # train_loop drives a single optimizer: fail here rather than in the first fit
        if len(self.optimizers) > 1:
            raise PybiscusValueException(
                f"{type(model).__name__}: multiple optimizers are not supported by the Fabric training loop"
            )
        check_schedulers_monitor(self.schedulers, model)

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
        logm.console.log(f"[Client] get_parameters, config: {config}")
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        logm.console.log("[Client] set_parameters")
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        logm.console.log(f"[Client {self.cid}] fit, config: {config}")
        self.set_parameters(parameters)
        metrics = {}

        if self.pre_train_val:
            logm.console.log(
                f"Round {config['server_round']}, pre train validation started..."
            )
            results_pre_train = test_loop(
                self.fabric, self.model, self._validation_dataloader
            )
            for key, val in results_pre_train.items():
                metrics[f"{key}_pre_train_val"] = val

        logm.console.log(f"Round {config['server_round']}, training Started...")

        results_train = train_loop(
            self.fabric,
            self.model,
            self._train_dataloader,
            self.optimizers,
            epochs=config["local_epochs"],
            schedulers=self.schedulers,
        )
            
        logm.console.log(f"Training Finished! Loss is {results_train['loss']}")
        metrics["cid"] = self.cid
        for key, val in results_train.items():
            metrics[key] = val
        return self.get_parameters(config={}), self.num_examples["trainset"], metrics

    def evaluate(self, parameters, config):
        logm.console.log(f"[Client {self.cid}] evaluate, config: {config}")
        self.set_parameters(parameters)
        metrics = {}
        logm.console.log(f"Round {config['server_round']}, evaluation Started...")
        results_evaluate = test_loop(
            self.fabric, self.model, self._validation_dataloader
        )
        logm.console.log(
            f"Evaluation finished! Loss is {results_evaluate['loss']}, metric {list(results_evaluate.keys())[0]} is {results_evaluate[list(results_evaluate.keys())[0]]}"
        )
        metrics["cid"] = self.cid
        for key, val in results_evaluate.items():
            metrics[key] = val
        return results_evaluate["loss"], self.num_examples["valset"], metrics
