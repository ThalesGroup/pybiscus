from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field
from torchmetrics import Accuracy

from cnn.cnn import net

# ------------------------------------------------------------------------------------

class ConfigCNN(BaseModel):
    """A Pydantic Model to validate the LitCNN config given by the user.

    Attributes
    ----------
    input_shape: int   = number of channels of the input
    mid_shape:   int   = number of channels of the second convolutional layer
    n_classes:   int   = number of classes
    lr:          float = the learning rate
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_shape: int   = Field( default=3,     description="number of channels of the input" )
    mid_shape:   int   = Field( title="Channels of the second layer", default=6,     description="number of channels of the second convolutional layer" )
    n_classes:   int   = Field( default=10,    description="number of classes" )
    lr:          float = Field( default=0.001, description="the learning rate" )

    model_config = ConfigDict(extra="forbid")

#        --------------------

class ConfigModel_Cifar10(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Cifar 10"

    name: Literal["cifar"]
    config: ConfigCNN

    model_config = ConfigDict(extra="forbid")

# ------------------------------------------------------------------------------------

class CNNSignature(TypedDict):
    loss: torch.Tensor
    accuracy: torch.Tensor

#        --------------------

class LitCNN(pl.LightningModule):
    """A small convolutional network for the 32 x 32 colour images of CIFAR-10 (data `cifar`): reports
    its loss and accuracy."""

    @override
    def __init__( self, input_shape: int, mid_shape: int, n_classes: int, lr: float, _logging: bool = False,):
        super().__init__()
        
        self.save_hyperparameters()

        # memo parameters
        self.input_shape = input_shape
        self.mid_shape   = mid_shape
        self.n_classes   = n_classes
        self.lr          = lr
        self._logging    = _logging

        self.model       = net( input_shape=self.input_shape, mid_shape=self.mid_shape, n_classes=self.n_classes,)
        self.loss        = nn.CrossEntropyLoss()
        self.accuracy    = Accuracy(task="multiclass", num_classes=self.n_classes, top_k=1)
        self._signature  = CNNSignature

    @property
    def signature(self):
        return self._signature

    def signatures(self, mode):
        return self._signature

    @override
    def forward(self, images):
        return self.model(images)

    @override
    def training_step(self, batch: torch.Tensor, batch_idx) -> CNNSignature:
        signal, labels = batch

        outputs = self.forward(signal)
        loss    = self.loss(outputs, labels)
        acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

        if self._logging:
            self.log("train_loss", loss, prog_bar=True)
            self.log("train_acc",  acc,  prog_bar=True)

        return {"loss": loss, "accuracy": acc}

    @override
    def validation_step(self, batch: torch.Tensor, batch_idx) -> CNNSignature:
        signal, labels = batch

        outputs = self.forward(signal)
        loss    = self.loss(outputs, labels)
        acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

        if self._logging:
            self.log("val_loss", loss, prog_bar=True)
            self.log("val_acc",  acc,  prog_bar=True)

        return {"loss": loss, "accuracy": acc}

    @override
    def test_step(self, batch: torch.Tensor, batch_idx) -> CNNSignature:
        signal, labels = batch

        outputs = self.forward(signal)
        loss    = self.loss(outputs, labels)
        acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

        if self._logging:
            self.log("test_loss", loss, prog_bar=True)
            self.log("test_acc",  acc,  prog_bar=True)

        return {"loss": loss, "accuracy": acc}

    @override
    def configure_optimizers(self) -> None:
        return torch.optim.SGD(self.parameters(), lr=self.lr, momentum=0.9)
