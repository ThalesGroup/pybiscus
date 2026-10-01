from dataclasses import dataclass
from typing import Optional

import torch
from rich.progress import track
from torch.optim.lr_scheduler import ReduceLROnPlateau

from pybiscus.core.pybiscusexception import PybiscusValueException
import pybiscus.core.pybiscus_logger as logm

torch.backends.cudnn.enabled = True


@dataclass
class SchedulerConfig:
    scheduler: object
    interval: str = "epoch"          # "epoch" | "step", as in Lightning's lr_scheduler dict
    frequency: int = 1
    monitor: Optional[str] = None
    # counts intervals over the whole session: the scheduler outlives a single fit (round)
    elapsed: int = 0

    def tick(self, metrics) -> None:
        self.elapsed += 1
        if self.elapsed % self.frequency:
            return
        if isinstance(self.scheduler, ReduceLROnPlateau):
            self.scheduler.step(float(metrics[self.monitor]))
        else:
            self.scheduler.step()


def check_schedulers_monitor(schedulers, net) -> None:

    # the Fabric loop only has training_step's metrics: no self.log registry and no
    # validation during fit (FL validation is a separate evaluate on the global model).
    # Never substitute another metric for the requested one
    plateaus = [s for s in schedulers if isinstance(s.scheduler, ReduceLROnPlateau)]
    if not plateaus:
        return
    available = sorted(signature_of_mode(net, "train").__required_keys__)
    for s in plateaus:
        if s.monitor is None:
            raise PybiscusValueException("ReduceLROnPlateau requires a 'monitor' metric")
        if s.monitor not in available:
            raise PybiscusValueException(
                f"ReduceLROnPlateau monitors '{s.monitor}', which is not a training metric; "
                f"available: {available} (no validation metric exists during fit)"
            )


def signature_of_mode(net, mode):
    """
    check if a signatures function exist, call it with mode
    -> enable to have a different signature according to mode
    otherwise return uniq signature
    """

    if hasattr(net, "signatures") and callable(getattr(net, "signatures")):
        return net.signatures(mode)
    else:
        return net.signature


def batch_size_of(results, batch) -> Optional[int]:
    """the model may say it (a "batch_size" key in its step's results); otherwise the first dimension
    of the batch's inputs: batch[0] for an (inputs, targets) pair, the length of a list of samples
    of various shapes (detection images) rather than an image's channels"""

    if isinstance(results, dict) and results.get("batch_size") is not None:
        return int(results["batch_size"])
    first = batch[0] if isinstance(batch, (list, tuple)) and batch else batch
    if isinstance(first, dict):
        first = next((value for value in first.values() if isinstance(value, torch.Tensor)), None)
    if isinstance(first, torch.Tensor):
        return int(first.shape[0]) if first.dim() > 0 else None
    if isinstance(first, (list, tuple)):
        return len(first)
    return None


_unsized_warned = False


class BatchMean:
    """means over the examples of metrics given per batch: an unweighted mean of the batch means
    gave the last, partial batch the weight of a full one (x2 for 10000 examples in batches of
    32, up to x31 with a one-example last batch). Additive metrics only (a mean loss, an
    accuracy): an F1 or an AUC needs counts accumulated over the epoch"""

    def __init__(self, keys, device):
        self.device = device
        self.weighted = {key: torch.tensor(0.0, device=device) for key in keys}
        self.plain = {key: torch.tensor(0.0, device=device) for key in keys}
        self.examples = 0
        self.batches = 0
        self.sized = True

    def add(self, results, batch) -> None:
        global _unsized_warned
        size = batch_size_of(results, batch)
        if size is None:
            self.sized = False
            if not _unsized_warned:
                _unsized_warned = True
                logm.console.log("⚠️ batch size unknown (give a 'batch_size' key in the step's results): "
                                 "metrics averaged per batch, the last partial batch weighing as a full one")
        self.batches += 1
        self.examples += size or 0
        for key in self.plain:
            value = results[key]

            # hardening code --- begin ---
            if not isinstance(value, torch.Tensor):
                value = torch.tensor(value, device=self.device)

            if value.shape != self.plain[key].shape:
                value = value.reshape(self.plain[key].shape)
            # hardening code --- end ---

            value = value.detach()
            self.plain[key] += value
            if size:
                self.weighted[key] += value * size

    def means(self) -> dict:
        if self.sized and self.examples > 0:
            return {key: (value / self.examples).item() for key, value in self.weighted.items()}
        return {key: (value / max(1, self.batches)).item() for key, value in self.plain.items()}


def trainable_params(net) -> list:
    return [p for p in net.parameters() if p.requires_grad]


def squared_distance(params, reference_params) -> torch.Tensor:
    return sum((w - w0).pow(2).sum() for w, w0 in zip(params, reference_params))


def add_proximal_gradient(params, reference_params, mu: float) -> None:
    """adds mu * (w - w0), the gradient of mu/2 * ||w - w0||^2, to each parameter's gradient"""
    with torch.no_grad():
        with_grad = [(w, w0) for w, w0 in zip(params, reference_params) if w.grad is not None]
        if with_grad:
            ws, w0s = (list(t) for t in zip(*with_grad))
            torch._foreach_add_([w.grad for w in ws], torch._foreach_sub(ws, w0s), alpha=mu)
        # a parameter the batch left without gradient still gets the term's, as the loss term gave it
        for w, w0 in zip(params, reference_params):
            if w.grad is None:
                w.grad = mu * (w - w0)


def train_loop(fabric, net, trainloader, optimizer, epochs: int, verbose=False, schedulers=(),
               proximal_mu: float = 0.0, global_params=None):
    """Train the network on the training set."""

    net.train()

    proximal = global_params is not None and proximal_mu > 0
    if proximal:
        trainable = trainable_params(net)
    # FedProx's term goes straight into the gradients (one batched operation, no autograd graph:
    # it cost up to +36 % per step on a GPU as a loss term), unless the loss is scaled (mixed
    # precision), whose gradients the term would then not match
    proximal_in_gradient = proximal and getattr(getattr(fabric, "_precision", None), "scaler", None) is None

    if not optimizer:
        optimizer = None
    elif isinstance(optimizer, list) and len(optimizer) == 1:
        optimizer = optimizer[0]

    history = []
    for epoch in range(epochs):
        epoch_mean = BatchMean(signature_of_mode(net, "train").__required_keys__, net.device)
        for batch_idx, batch in track(
            enumerate(trainloader),
            total=len(trainloader),
            description="Training...",
        ):
            results = net.training_step(batch, batch_idx)
            loss = results["loss"]
            # FedProx: the term only steers the gradient, the reported loss stays the data one so
            # that its curves remain comparable with the other strategies'
            if proximal and not proximal_in_gradient:
                loss = loss + proximal_mu / 2 * squared_distance(trainable, global_params)

            if optimizer is not None:
                optimizer.zero_grad()
                fabric.backward(loss)
                if proximal_in_gradient:
                    add_proximal_gradient(trainable, global_params, proximal_mu)
                optimizer.step()

            for s in schedulers:
                if s.interval == "step":
                    s.tick(results)

            epoch_mean.add(results, batch)

        results_epoch = epoch_mean.means()
        history.append(dict(results_epoch))
        if epochs > 1:
            logm.console.log(
                f"Epoch {epoch + 1}/{epochs} "
                + " ".join(f"{key}={value:.4f}" for key, value in results_epoch.items())
            )

        for s in schedulers:
            if s.interval == "epoch":
                s.tick(results_epoch)

    # the plain keys describe the LAST local epoch only (the state of the model sent to the
    # server); with several epochs, each one is added as <key>_epoch_<i> so that the local
    # trajectory (client drift) stays visible. With a single epoch the output is unchanged
    if epochs > 1:
        for epoch_number, epoch_results in enumerate(history, 1):
            for key, value in epoch_results.items():
                results_epoch[f"{key}_epoch_{epoch_number}"] = value
    return results_epoch


def test_loop(fabric, net, testloader):
    """Evaluate the network on the entire test set."""
    # Alice: fabric is not used
    net.eval()

    with torch.no_grad():
        mean = BatchMean(signature_of_mode(net, "test").__required_keys__, net.device)
        for batch_idx, batch in track(
            enumerate(testloader),
            total=len(testloader),
            description="Validating...",
        ):

            results = net.test_step(batch, batch_idx)

            # ensure that result is a dict, make convertion if required 
            if isinstance(results, torch.Tensor):
                # result is just the loss tensor => put it into a dict
                results = {"loss": results}

            elif not isinstance(results, dict):
                # other format => convert to tensor and put it into a dict
                results = {"loss": torch.as_tensor(results)}

            mean.add(results, batch)

    return mean.means()
