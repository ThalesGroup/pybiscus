from typing import List

import lightning.pytorch as pl
import torch
import torch.nn as nn
from torchmetrics import Accuracy

from src.ml.models.cnn import net


class LitCNN(pl.LightningModule):
    def __init__(self, input_shape, mid_shape, n_classes, lr):
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

    def validation_step(self, batch: torch.Tensor, batch_idx) -> List[torch.Tensor]:
        signal, labels = batch
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        acc = self.accuracy(torch.max(outputs.data, 1)[1], labels)
        self.log("val_loss", loss, prog_bar=True)
        self.log("val_acc", acc, prog_bar=True)
        return {"loss": loss, "accuracy": acc}

    def test_step(self, batch: torch.Tensor, batch_idx) -> List[torch.Tensor]:
        signal, labels = batch
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        return loss

    def configure_optimizers(self) -> None:
        return torch.optim.SGD(self.parameters(), lr=self.lr, momentum=0.9)
