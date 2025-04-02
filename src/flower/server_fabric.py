from collections import OrderedDict
from typing import Callable, Optional, Union, Dict, ClassVar

import flwr as fl
import numpy as np
import torch
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.pytorch import LightningModule
from pydantic import BaseModel, ConfigDict, Field

from src.console import console
from src.flower.client_fabric import ConfigFabric
from src.flower.strategies import ConfigFabricStrategy
from src.ml.loops_fabric import test_loop
from src.ml.registry import ModelConfig, DataConfig

class ConfigLogger(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "logger"

    subdir: str = Field( default="/experiments/node", description="!!!!!!!" )

    model_config = ConfigDict(extra="forbid")

    # to emulate a dict
    def __getitem__(self, attName):
        return getattr(self, attName, None)

class ConfigStrategy(BaseModel):
    """name: str = fabric is the only possible value"""

    PYBISCUS_CONFIG: ClassVar[str] = "strategy"

    name: str = "fabric"

    config: ConfigFabricStrategy

    model_config = ConfigDict(extra="forbid")

class ConfigSslServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    root_certificate_path   = root certificate path
    server_certificate_path = server certificate path
    server_private_key_path = private key path
    """

    PYBISCUS_ALIAS: ClassVar[str] = "SSL Flower server"

    root_certificate_path:   str = Field( default=None, description="root certificate path" )
    server_certificate_path: str = Field( default=None, description="server certificate path" )
    server_private_key_path: str = Field( default=None, description="server private key path" )

    model_config = ConfigDict(extra="forbid")

class ConfigServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    num_rounds: int    = the number of rounds for the FL session.
    server_adress: str = the server adress and port
    root_dir: str      = the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    logger: str        = the config for the logger.
    strategy           = arguments for the needed Strategy
    fabric             = keywords for the Fabric instance
    model              = keywords for the LightningModule used
    data               = keywords for the LightningDataModule used.
    ssl                = keywords for https usage
    clients_configs    = list of paths to the configuration files used by all clients.
    save_on_train_end: optional, default to False = states if the weights of the model are saved at the very end of FL session, the path is fabric.logger.log_dir + "/checkpoint.pt"
    """

    PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus server configuration"

    num_rounds:        int = 10
    server_adress:     str = '[::]:3333'
    root_dir:          str = "${oc.env:PWD}"
    client_configs:    list[str] = Field(default=None)
    save_on_train_end: bool = False

    logger:            Optional[ConfigLogger]
    strategy:          ConfigStrategy
    fabric:            ConfigFabric
    model:             ModelConfig
    data:              DataConfig
    ssl:               Optional[ConfigSslServer] = None

    model_config = ConfigDict(extra="forbid")


def set_params(model: torch.nn.ModuleList, params: list[np.ndarray]):
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
    testset: torch.utils.data.DataLoader,
    model: LightningModule,
    fabric: Fabric,
) -> Callable[[fl.common.NDArrays], Optional[tuple[float, float]]]:
    def evaluate(
        server_round: int, parameters: fl.common.NDArrays, config: dict[str, Scalar]
    ) -> Optional[tuple[float, float]]:
        set_params(model, parameters)

        results = test_loop(fabric=fabric, net=model, testloader=testset)
        return results["loss"], results

    return evaluate


def weighted_average(metrics: list[tuple[int, Metrics]]) -> Metrics:
    _set_common_keys = set()
    for _, metric in metrics:
        # the "cid" metric is a false one, need to pop it out
        metric.pop("cid")
        if _set_common_keys is set():
            _set_common_keys = set(metric.keys())
        else:
            _set_common_keys = _set_common_keys.intersection(set(metric.keys()))
    num_examples = sum([num_examples for num_examples, _ in metrics])
    outputs = {
        key: sum(num * metric[key] / num_examples for num, metric in metrics)
        for key in _set_common_keys
    }
    console.log(f"Averaged metrics: {outputs}")
    return outputs
