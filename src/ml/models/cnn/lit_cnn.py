from typing import Literal

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict
from torchmetrics import Accuracy

from src.ml.models.cnn.cnn import net


class ConfigCNN(BaseModel):
    """A Pydantic Model to validate the LitCNN config given by the user.

    Attributes
    ----------
    input_shape:
        number of channels of the input
    mid_shape: int
        number of channels of the second convolutional layer
    n_classes:
        number of classes
    lr: float
        the learning rate
    """

    input_shape: int
    mid_shape: int
    n_classes: int
    lr: float

    model_config = ConfigDict(extra="forbid")


class ConfigModel_Cifar10(BaseModel):
    name: Literal["cifar"]
    config: ConfigCNN

    model_config = ConfigDict(extra="forbid")


class LitCNN(pl.LightningModule):
    def __init__(self, input_shape: int, mid_shape: int, n_classes: int, lr: float):
        super().__init__()
        self.save_hyperparameters()
        self.input_shape = input_shape
        self.mid_shape = mid_shape
        self.n_classes = n_classes
        self.lr = lr
        self.model = net(
            input_shape=self.input_shape,
            mid_shape=self.mid_shape,
            n_classes=self.n_classes,
        )
        self.loss = nn.CrossEntropyLoss()
        self.accuracy = Accuracy(task="multiclass", num_classes=self.n_classes, top_k=1)

    def forward(self, images):
        return self.model(images)

    def training_step(self, batch: torch.Tensor, batch_idx) -> torch.Tensor:
        signal, labels = batch
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        acc = self.accuracy(torch.max(outputs.data, 1)[1], labels)
        self.log("train_loss", loss, prog_bar=True)
        return {"loss": loss, "accuracy": acc}

    def validation_step(self, batch: torch.Tensor, batch_idx) -> list[torch.Tensor]:
        signal, labels = batch
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        acc = self.accuracy(torch.max(outputs.data, 1)[1], labels)
        self.log("val_loss", loss, prog_bar=True)
        self.log("val_acc", acc, prog_bar=True)
        return {"loss": loss, "accuracy": acc}

    def test_step(self, batch: torch.Tensor, batch_idx) -> list[torch.Tensor]:
        signal, labels = batch
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        return loss

    def configure_optimizers(self) -> None:
        return torch.optim.SGD(self.parameters(), lr=self.lr, momentum=0.9)
