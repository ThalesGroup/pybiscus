import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10


# Alice: je trouve ce fichier redondant avec le datamodule, pourquoi ne pas factorisé et faire de load_data une fonction du datamodule ?
def load_data(
    data_dir_train: str = None,
    data_dir_val: str = None,
    data_dir_test: str = None,
    batch_size: int = 1,
    stage: str = "fit",
):
    """Load CIFAR-10 (training and test set)."""
    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]
    )
    if stage == "fit":
        trainset = CIFAR10(
            root=data_dir_train, train=True, download=True, transform=transform
        )
        valset = CIFAR10(
            root=data_dir_val, train=False, download=True, transform=transform
        )
        trainloader = DataLoader(trainset, batch_size=batch_size, shuffle=True)
        valloader = DataLoader(valset, batch_size=batch_size)
        num_examples = {"trainset": len(trainset), "valset": len(valset)}
        return trainloader, valloader, num_examples
    if stage == "test":
        testset = CIFAR10(
            root=data_dir_test, train=False, download=True, transform=transform
        )
        testloader = DataLoader(testset, batch_size=batch_size, shuffle=False)
        return testloader
