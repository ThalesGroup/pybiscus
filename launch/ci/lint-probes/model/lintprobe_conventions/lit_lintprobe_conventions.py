from typing import ClassVar, Literal, TypedDict

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field


class ConfigLintprobeConventions(BaseModel):  # expect: extra-forbid
    """the settings of the lintprobe_conventions model"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_dim: int = Field(default=4, ge=1, description="features per example, the data's (randomvector: feature_dim)")
    hidden: int = Field(default=16, ge=1, description="units of the hidden layer")
    lr: float = Field(default=0.01, gt=0, description="learning rate of the Adam optimizer")
    momentum: float = 0.0  # expect: description


class ConfigModel_LintprobeConventions(BaseModel):  # expect: alias


    # the registry key: what a configuration's `model: name:` gives
    name: Literal["lintprobe_conventions"]
    config: ConfigLintprobeConventions

    model_config = ConfigDict(extra="forbid")


# the training and test loops average these keys over the batches; the first one after loss is the
# metric the session's GUI follows
class LintprobeConventionsSignature(TypedDict):
    loss: torch.Tensor
    mae: torch.Tensor


class LitLintprobeConventions(pl.LightningModule):
    """TODO: what the lintprobe_conventions model learns, in one paragraph: the plugins reference shows it."""

    # the arguments are the fields of ConfigLintprobeConventions
    def __init__(self, input_dim: int, hidden: int, lr: float):
        super().__init__()
        self.save_hyperparameters()
        self.net = nn.Sequential(nn.Linear(input_dim, hidden), nn.ReLU(), nn.Linear(hidden, input_dim))
        self.loss_fn = nn.MSELoss()

    @property
    def signature(self):
        return LintprobeConventionsSignature

    def forward(self, x):
        print(x.shape)  # expect: print
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
        reporting_path = None  # expect: reporting-outputs
        return torch.optim.Adam(self.parameters(), lr=self.hparams.lr)
