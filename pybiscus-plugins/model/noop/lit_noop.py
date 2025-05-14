from typing import ClassVar, Literal, TypedDict
from pydantic import BaseModel, ConfigDict
import lightning.pytorch as pl
import torch
import torch.nn as nn

class ConfigNoop(BaseModel):
    """A Pydantic Model to validate the LitNoop config given by the user.

    Attributes
    ----------
    None
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigModel_Noop(BaseModel):
    """Pydantic BaseModel to validate Configuration for "noop" Model.

    Attributes
    ----------
    name:
        designation "noop" to choose
    """

    PYBISCUS_ALIAS: ClassVar[str] = "Noop"
    name: Literal["noop"]
    config: ConfigNoop
    model_config = ConfigDict(extra="forbid")

class NoopModel(nn.Module):
    def __init__(self):
        super(NoopModel, self).__init__()

    def forward(self, x):
        return x

class NoopSignature(TypedDict):
    loss: torch.Tensor
    accuracy: torch.Tensor

class NoopModel(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        return x

class LitNoop(pl.LightningModule):
    def __init__(self, empty_configuration: bool):
        super().__init__()
        self.model = NoopModel()
        self.loss_fn = nn.MSELoss()
        self._signature = NoopSignature

    @property
    def signature(self):
        return self._signature

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        return { "loss": torch.zeros(1), "accuracy": torch.ones(1) }

    def validation_step(self, batch: torch.Tensor, batch_idx):
        return { "loss": torch.zeros(1), "accuracy": torch.ones(1) }

    def test_step(self, batch: torch.Tensor, batch_idx):
        loss = torch.zeros(1)        
        return loss

    def configure_optimizers(self):
        return None
