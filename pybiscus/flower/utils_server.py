from collections import OrderedDict
from typing import Callable, Optional

import flwr as fl
import numpy as np
import torch
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.pytorch import LightningModule

import pybiscus.core.pybiscus_logger as logm
from pybiscus.ml.loops_fabric import test_loop

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


def weighted_average_old(metrics: list[tuple[int, Metrics]]) -> Metrics:

    print(f"@@@@ metrics: {metrics}")

    _set_common_keys = set()

    for _, metric in metrics:
        if not _set_common_keys:
            _set_common_keys = set(metric.keys())
        else:
            _set_common_keys = _set_common_keys.intersection(set(metric.keys()))
        
    print(f"@@@@ keys1: {_set_common_keys}")
    # the "cid" metric is a false one, need to pop it out
    # Q: should we do the same for all metrics that are str ?
    _set_common_keys.discard("cid")
    _set_common_keys.discard("relay_cid")
    _set_common_keys.discard("relay_type")
    _set_common_keys.discard("timestamp")
    print(f"@@@@ keys2: {_set_common_keys}")

    num_examples = sum([num_examples for num_examples, _ in metrics])
    print(f"@@@@ num: {num_examples}")

    if num_examples == 0:
        outputs = {}
    else:
        outputs = {
            key: sum(num * metric[key] / num_examples for num, metric in metrics)
            for key in _set_common_keys
        }

    logm.console.log(f"Averaged metrics: {outputs}")
    
    return outputs

def weighted_average(metrics: list[tuple[int, Metrics]]) -> Metrics:
    
    print(f"@@@@ metrics: {metrics}")

    _set_common_keys = set()

    for _, metric in metrics:
        if not _set_common_keys:
            _set_common_keys = set(metric.keys())
        else:
            _set_common_keys = _set_common_keys.intersection(set(metric.keys()))
        
    print(f"@@@@ keys1: {_set_common_keys}")
    
    # Filter to keep only numeric keys
    numeric_keys = set()
    
    for key in _set_common_keys:
        # Check if the key contains numeric values
        sample_values = [metric[key] for _, metric in metrics if key in metric]
        if sample_values and isinstance(sample_values[0], (int, float)):
            numeric_keys.add(key)
    
    _set_common_keys = numeric_keys
    print(f"@@@@ keys2: {_set_common_keys}")

    num_examples = sum([num_examples for num_examples, _ in metrics])
    print(f"@@@@ num: {num_examples}")

    if num_examples == 0:
        outputs = {}
    else:
        outputs = {
            key: sum(num * metric[key] / num_examples for num, metric in metrics)
            for key in _set_common_keys
        }

    logm.console.log(f"Averaged metrics: {outputs}")
    
    return outputs