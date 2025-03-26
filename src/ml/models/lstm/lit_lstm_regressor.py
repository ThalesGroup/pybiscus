from typing import Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict

from src.ml.models.lstm.lstm_regressor import LSTMRegressor


class ConfigLSTM(BaseModel):
    """A Pydantic Model to validate the LitCNN config given by the user.

    Attributes
    ----------
    n_features:
        number of features of the input
    hidden_units: int
        number of hiddent units of the LSTM
    lr: float
        the learning rate
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    n_features: int = 24
    hidden_units: int = 12
    lr: float = 0.001

    model_config = ConfigDict(extra="forbid")


class ConfigModel_LSTM(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "LSTM"

    name: Literal["lstm"]
    config: ConfigLSTM

    model_config = ConfigDict(extra="forbid")


class LSTMSignature(TypedDict):
    loss: torch.Tensor


class LitLSTMRegressor(pl.LightningModule):
    def __init__(
        self,
        n_features: int,
        hidden_units: int,
        lr: float,
        _logging: bool = False,
    ):
        super().__init__()
        self.save_hyperparameters()
        self.n_features = n_features
        self.hidden_units = hidden_units
        self.lr = lr
        self._logging = _logging
        self.model = LSTMRegressor(
            n_features=self.n_features,
            hidden_units=self.hidden_units,
        )
        self.loss = nn.MSELoss()
        self._signature = LSTMSignature

    @property
    def signature(self):
        return self._signature

    def forward(self, images):
        return self.model(images)

    def training_step(self, batch: torch.Tensor, batch_idx) -> LSTMSignature:
        signal, labels = batch
        signal  = signal.to(torch.float32)
        labels  = labels.to(torch.float32)
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        if self._logging:
            self.log("train_loss", loss, prog_bar=True)
        return {"loss": loss}

    def validation_step(self, batch: torch.Tensor, batch_idx) -> LSTMSignature:
        signal, labels = batch
        signal  = signal.to(torch.float32)
        labels  = labels.to(torch.float32)
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        if self._logging:
            self.log("val_loss", loss, prog_bar=True)
        return {"loss": loss}

    def test_step(self, batch: torch.Tensor, batch_idx) -> torch.Tensor:
        signal, labels = batch
        signal  = signal.to(torch.float32)
        labels  = labels.to(torch.float32)
        outputs = self.forward(signal)
        loss = self.loss(outputs, labels)
        return loss

    def configure_optimizers(self) -> None:
        return torch.optim.Adam(self.parameters(), lr=self.lr)
