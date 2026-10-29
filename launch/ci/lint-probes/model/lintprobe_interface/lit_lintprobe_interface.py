from typing import ClassVar, Literal, TypedDict

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field


class ConfigLintprobeInterface(BaseModel):
    """the settings of the lintprobe_interface model"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_dim: int = Field(default=4, ge=1, description="features per example, the data's (randomvector: feature_dim)")
    hidden: int = Field(default=16, ge=1, description="units of the hidden layer")
    lr: float = Field(default=0.01, gt=0, description="learning rate of the Adam optimizer")

    model_config = ConfigDict(extra="forbid")


class ConfigModel_LintprobeInterface(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "LintprobeInterface"

    # the registry key: what a configuration's `model: name:` gives
    name: Literal["lintprobe_interface"]
    config: ConfigLintprobeInterface

    model_config = ConfigDict(extra="forbid")


# the training and test loops average these keys over the batches; the first one after loss is the
# metric the session's GUI follows
class LintprobeInterfaceSignature(TypedDict):
    loss: torch.Tensor
    mae: torch.Tensor


class LitLintprobeInterface(nn.Module):  # expect: interface
    """TODO: what the lintprobe_interface model learns, in one paragraph: the plugins reference shows it."""

    # the arguments are the fields of ConfigLintprobeInterface
    def __init__(self, input_dim: int, hidden: int, lr: float):
        super().__init__()
        self.save_hyperparameters()
        self.net = nn.Sequential(nn.Linear(input_dim, hidden), nn.ReLU(), nn.Linear(hidden, input_dim))
        self.loss_fn = nn.MSELoss()

    @property
    def signature(self):
        return LintprobeInterfaceSignature

    def forward(self, x):
        return self.net(x)

    def _step(self, batch):
        x, y = batch
        y_hat = self(x)
        return {"loss": self.loss_fn(y_hat, y), "mae": (y_hat - y).abs().mean()}

    def training_step(self, batch, batch_idx):
        return self._step(batch)

    def validation_step(self, batch, batch_idx):
        return self._step(batch)

    def test_step(self, batch, batch_idx):
        return self._step(batch)

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.lr)
