import torch
from rich.progress import track

torch.backends.cudnn.enabled = True


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


def train_loop(fabric, net, trainloader, optimizer, epochs: int, verbose=False):
    """Train the network on the training set."""

    net.train()

    if not optimizer:
        optimizer = None
    elif isinstance(optimizer, list) and len(optimizer) == 1:
        optimizer = optimizer[0]
    
    for _ in range(epochs):
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
