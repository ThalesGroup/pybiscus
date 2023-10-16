import torch
from rich.progress import track

torch.backends.cudnn.enabled = True


def train_loop(fabric, net, trainloader, optimizer, epochs: int, verbose=False):
    """Train the network on the training set."""

    net.train()
    for epoch in range(epochs):
        correct, epoch_loss = 0, 0.0
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

            epoch_loss += loss
            correct += results["accuracy"]
        epoch_loss /= len(trainloader)
        epoch_acc = correct / len(trainloader)
    return epoch_loss.item(), epoch_acc.item()


def test_loop(fabric, net, testloader):
    """Evaluate the network on the entire test set."""
    # Alice: fabric is not used
    correct, loss = 0, 0.0
    net.eval()

    with torch.no_grad():
        for batch_idx, batch in track(
            enumerate(testloader),
            total=len(testloader),
            description="Validating...",
        ):
            results = net.validation_step(batch, batch_idx)
            loss += results["loss"]
            correct += results["accuracy"]

    loss /= len(testloader)
    accuracy = correct / len(testloader)
    return loss.item(), accuracy.item()
