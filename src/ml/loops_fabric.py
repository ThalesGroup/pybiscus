import torch
from rich.progress import track

torch.backends.cudnn.enabled = True


def train_loop(fabric, net, trainloader, optimizer, epochs: int, verbose=False):
    """Train the network on the training set."""

    net.train()
    for epoch in range(epochs):
        results_epoch = {
            key: torch.tensor(0.0, device=net.device)
            for key in net.signature.__required_keys__
        }
        for batch_idx, batch in track(
            enumerate(trainloader),
            total=len(trainloader),
            description="Training...",
        ):
            optimizer.zero_grad()
            results = net.training_step(batch, batch_idx)
            loss = results["loss"]
            fabric.backward(loss)
            optimizer.step()

            for key in results_epoch.keys():
                results_epoch[key] += results[key]
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
            for key in net.signature.__required_keys__
        }
        for batch_idx, batch in track(
            enumerate(testloader),
            total=len(testloader),
            description="Validating...",
        ):
            results = net.validation_step(batch, batch_idx)
            for key in results_epoch.keys():
                results_epoch[key] += results[key]

    for key in results_epoch.keys():
        results_epoch[key] /= len(testloader)
        results_epoch[key] = results_epoch[key].item()
    return results_epoch
