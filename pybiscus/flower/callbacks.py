import functools
from collections import OrderedDict
from typing import Callable, Optional

import flwr as fl
import numpy as np
import torch
from flwr.common import Metrics, Scalar
from lightning.fabric import Fabric
from lightning.pytorch import LightningModule

from pybiscus.console import console
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
    """Return an evaluation function that uses the given model, dataset and Fabric.

    Parameters
    ----------
    testset : torch.utils.data.DataLoader
        the evaluation dataset, server-side.
    model : LightningModule
        the model trained federatively.
    fabric : Fabric
        a Fabric instance, useful here for the Tensorboard logging.

    Returns
    -------
    Callable[[fl.common.NDArrays], Optional[tuple[float, float]]]
        the evaluation function wrapped by helper functions.
    """

    def evaluate(
        server_round: int, parameters: fl.common.NDArrays, config: dict[str, Scalar]
    ) -> Optional[tuple[float, float]]:
        set_params(model, parameters)

        results = test_loop(fabric=fabric, net=model, testloader=testset)
        for key, value in results.items():
            console.log(f"Test at round {server_round}, {key} is {value:.3f}")
            fabric.log(f"val_{key}_glob", value, step=server_round)
        return results["loss"], results

    return evaluate


def clean_metrics(metrics):
    """Clean metrics by popping cid key and keeping only common keys to all metrics.

    Parameters
    ----------
    metrics : _type_
        _description_

    Returns
    -------
    _type_
        _description_
    """
    _set_common_keys = set()
    for _, metric in metrics:
        # the "cid" metric is a false one, need to pop it out
        metric.pop("cid")
        if _set_common_keys == set():
            _set_common_keys = set(metric.keys())
        else:
            _set_common_keys = _set_common_keys.intersection(set(metric.keys()))
    _metrics = [
        (num, {key: metric[key] for key in _set_common_keys}) for num, metric in metrics
    ]
    return _metrics


def better_aggregate(func, fabric, stage, start_server_round: int = 1):
    """Wrap a given metrics aggregation function with Fabric and Rich helpers.

    Attributes
    ----------
    server_round: int
        a stateful variable used to track the current server round.
        Use a simple update by one at the end of the aggragation.

    Parameters
    ----------
    func :
        a function for the aggregation of metrics.
    fabric :
        a Fabric instance used for Tensorboard logging.
    stage :
        the stage at which the aggregation is used, like "val" or "fit".
    start_server_round : int, optional
        the index for the start of the server rounds, by default 1

    Returns
    -------
    _type_
        _description_
    """

    @functools.wraps(func)
    def wrap_better_aggregate(metrics: list[tuple[int, Metrics]], *args, **kwargs):
        for _, metric in metrics:
            for key, value in metric.items():
                fabric.log(
                    f"{stage}_{key}_{metric['cid']}",
                    value,
                    step=wrap_better_aggregate.server_round,
                )
        _metrics = clean_metrics(metrics)
        outputs = func(_metrics, *args, **kwargs)
        console.log(
            f"At Stage {stage} and round {wrap_better_aggregate.server_round}, aggregated metrics are: {outputs}"
        )
        wrap_better_aggregate.server_round += 1
        return outputs

    wrap_better_aggregate.server_round = start_server_round
    return wrap_better_aggregate


def weighted_average_metrics(metrics: list[tuple[int, Metrics]]) -> Metrics:
    num_examples = sum([num_examples for num_examples, _ in metrics])
    _common_keys = metrics[0][1].keys()
    outputs = {
        key: sum(num * metric[key] / num_examples for (num, metric) in metrics)
        for key in _common_keys
    }
    return outputs
