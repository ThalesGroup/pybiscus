from collections import OrderedDict
from typing import Callable, Optional, Union

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




class ConfigStrategy(BaseModel):
    name: str
    config: ConfigFabricStrategy

    model_config = ConfigDict(extra="forbid")

class ConfigSslServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    root_certificate_path:
        root certificate path
    server_certificate_path:
        server certificate path
    server_private_key_path:
        private key path
    """

    root_certificate_path: str
    server_certificate_path: str
    server_private_key_path: str

    model_config = ConfigDict(extra="forbid")

class ConfigServer(BaseModel):
    """A Pydantic Model to validate the Server configuration given by the user.

    Attributes
    ----------
    num_rounds:
        the number of rounds for the FL session.
    server_adress:
        the server adress and port
    root_dir:
        the path to a "root" directory, relatively to which can be found Data, Experiments and other useful directories
    logger:
        a doctionnary holding the config for the logger.
    strategy:
        a dictionnary holding (partial) arguments for the needed Strategy
    fabric:
        a dictionnary holding all necessary keywords for the Fabric instance
    model:
        a dictionnary holding all necessary keywords for the LightningModule used
    data:
        a dictionnary holding all necessary keywords for the LightningDataModule used.
    ssl: dict
        a dictionnary holding all necessary options for https usage
    clients_configs:
        a list of paths to the configuration files used by all clients.
    save_on_train_end: optional, default to False
        if true, the weights of the model are saved at the very end of the Federated Learning.
        The path is fabric.logger.log_dir + "/checkpoint.pt"
    """

    num_rounds: int
    server_adress: str
    root_dir: str
    logger: dict
    strategy: ConfigStrategy
    fabric: ConfigFabric
    model: ModelConfig
    data: DataConfig
    ssl: Optional[ConfigSslServer] = None
    client_configs: list[str] = Field(default=None)
    save_on_train_end: bool = Field(default=False)

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
