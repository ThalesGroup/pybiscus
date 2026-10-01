from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field
from torchmetrics import Accuracy

# The model of the mnist data plugin: the cifar CNN expects 32 x 32 images, MNIST's are 28 x 28.

class ConfigMnistCNN(BaseModel):
    """a small CNN for the 28 x 28 grey images of MNIST"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    hidden:    int   = Field(default=128, ge=1, description="units of the hidden dense layer")
    n_classes: int   = Field(default=10, ge=2, description="number of classes")
    lr:        float = Field(default=0.001, gt=0, description="learning rate of the Adam optimizer")

    model_config = ConfigDict(extra="forbid")


class ConfigModel_MnistCNN(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "MNIST CNN"

    name: Literal["mnist_cnn"]
    config: ConfigMnistCNN

    model_config = ConfigDict(extra="forbid")


class MnistCNNSignature(TypedDict):
    loss: torch.Tensor
    accuracy: torch.Tensor


def mnist_net(hidden: int, n_classes: int) -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(1, 32, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # 32 x 14 x 14
        nn.Conv2d(32, 64, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 64 x 7 x 7
        nn.Flatten(),
        nn.Linear(64 * 7 * 7, hidden), nn.ReLU(),
        nn.Linear(hidden, n_classes),
    )


class LitMnistCNN(pl.LightningModule):

    @override
    def __init__(self, hidden: int, n_classes: int, lr: float):
        super().__init__()
        self.save_hyperparameters()

        self.lr        = lr
        self.model     = mnist_net(hidden, n_classes)
        self.loss      = nn.CrossEntropyLoss()
        self.accuracy  = Accuracy(task="multiclass", num_classes=n_classes, top_k=1)
        self._signature = MnistCNNSignature

    @property
    def signature(self):
        return self._signature

    def signatures(self, mode):
        return self._signature

    @override
    def forward(self, images):
        return self.model(images)

    def _step(self, batch) -> MnistCNNSignature:
        images, labels = batch
        outputs = self.forward(images)
        return {"loss": self.loss(outputs, labels), "accuracy": self.accuracy(outputs.argmax(dim=1), labels)}

    @override
    def training_step(self, batch, batch_idx) -> MnistCNNSignature:
        return self._step(batch)

    @override
    def validation_step(self, batch, batch_idx) -> MnistCNNSignature:
        return self._step(batch)

    @override
    def test_step(self, batch, batch_idx) -> MnistCNNSignature:
        return self._step(batch)

    @override
    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.lr)
