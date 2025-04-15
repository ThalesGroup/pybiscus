from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
import torch.optim as optim
from pydantic import BaseModel, ConfigDict

from src.ml.data.randomvector.randomvector_datamodule import RandomVectorLightningDataModule

# ------------------------------------------------------------------------------------

class ConfigLinearRegression(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_dim:          int
    output_dim:         int
    learning_rate:      float
    accuracy_threshold: float

    model_config = ConfigDict(extra="forbid")

#        --------------------

class ConfigModel_LinearRegression(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Linear regression"

    name: Literal["linearregression"]
    config: ConfigLinearRegression

    model_config = ConfigDict(extra="forbid")

# ------------------------------------------------------------------------------------

class LinearRegressionSignature(TypedDict):
    loss: torch.Tensor

#        --------------------

# Définition du LightningModule
class LitLinearRegression(pl.LightningModule):

    @override
    def __init__(self, input_dim, output_dim, learning_rate=1e-3, accuracy_threshold=0.5, _logging: bool = False,):
        super(LitLinearRegression, self).__init__()

        self.save_hyperparameters()

        self._logging    = _logging

        # Définir une simple couche linéaire
        self.linear = nn.Linear(input_dim, output_dim)

        # Définir le critère de perte
        self.criterion = nn.MSELoss()
        self.accuracy_threshold = accuracy_threshold

        self._signature  = LinearRegressionSignature

    @property
    def signature(self):
        return self._signature

    @override
    def forward(self, x):
        return self.linear(x)

    @override
    def training_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.criterion(y_hat, y)
        acc = self.calculate_accuracy(y_hat, y)

        if self._logging:
            self.log('train_loss', loss)

        #return loss
        return {"loss": loss, "accuracy": acc}

    @override
    def validation_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.criterion(y_hat, y)
        acc = self.calculate_accuracy(y_hat, y)

        if self._logging:
            self.log("val_loss", loss, prog_bar=True)
            self.log("val_acc",  acc,  prog_bar=True)
        
        #return loss
        return {"loss": loss, "accuracy": acc}

    @override
    def test_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.criterion(y_hat, y)
        
        #self.log('test_loss', loss)

        return loss

    def calculate_accuracy(self, y_hat, y):
        # Calculer l'accuracy basée sur un seuil
        correct = torch.abs(y_hat - y) < self.accuracy_threshold
        accuracy = correct.float().mean()
        return accuracy

    @override
    def configure_optimizers(self):
        return optim.Adam(self.parameters(), lr=self.hparams.learning_rate)

if __name__ == "__main__":

    # Exemple d'utilisation
    input_dim = 1
    output_dim = 1

    # Initialiser le DataModule
    data_module = RandomVectorLightningDataModule(num_samples=320, feature_dim=input_dim, batch_size=32)

    # Initialiser le modèle
    model = LitLinearRegression(input_dim=input_dim, output_dim=output_dim, _logging = True )

    # Initialiser le Trainer
    trainer = pl.Trainer(max_epochs=10)

    # Entraîner le modèle
    trainer.fit(model, datamodule=data_module)

