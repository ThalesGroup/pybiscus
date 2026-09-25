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


def train_loop(fabric, net, trainloader, optimizer, epochs: int, verbose=False, schedulers=()):
    """Train the network on the training set."""

    net.train()

    if not optimizer:
        optimizer = None
    elif isinstance(optimizer, list) and len(optimizer) == 1:
        optimizer = optimizer[0]

    history = []
    for epoch in range(epochs):
        results_epoch = {
            key: torch.tensor(0.0, device=net.device)
            for key in signature_of_mode(net, "train").__required_keys__
        }
        for batch_idx, batch in track(
            enumerate(trainloader),
            total=len(trainloader),
            description="Training...",
        ):
            results = net.training_step(batch, batch_idx)
            loss = results["loss"]

            if optimizer is not None:
                optimizer.zero_grad()
                fabric.backward(loss)
                optimizer.step()

            for s in schedulers:
                if s.interval == "step":
                    s.tick(results)

            for key in results_epoch.keys():
                value = results[key]

                # hardening code --- begin ---
                if not isinstance(value, torch.Tensor):
                    value = torch.tensor(value, device=net.device)

                if value.shape != results_epoch[key].shape:
                    value = value.reshape(results_epoch[key].shape)
                # hardening code --- end ---

                results_epoch[key] += value

        for key in results_epoch.keys():
            results_epoch[key] /= len(trainloader)
            results_epoch[key] = results_epoch[key].item()

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
        results_epoch = {
            key: torch.tensor(0.0, device=net.device)
            for key in signature_of_mode(net, "test").__required_keys__
        }
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



            for key in results_epoch.keys():
                value = results[key]

                # hardening code --- begin ---
                if not isinstance(value, torch.Tensor):
                    value = torch.tensor(value, device=net.device)

                if value.shape != results_epoch[key].shape:
                    value = value.reshape(results_epoch[key].shape)
                # hardening code --- end ---

                results_epoch[key] += value

    for key in results_epoch.keys():
        results_epoch[key] /= len(testloader)
        results_epoch[key] = results_epoch[key].item()
    return results_epoch
