from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
import torch.optim as optim
from pydantic import BaseModel, ConfigDict
import pybiscus.core.pybiscus_logger as logm

# ------------------------------------------------------------------------------------

class ConfigLinearRegression(BaseModel):
    """
    Configuration for a simple linear regression model.

    Attributes:
        input_dim (int) = Dimension of the input features.
        output_dim (int) =  Dimension of the output targets.
        learning_rate (float) =  Learning rate used during model training.
        accuracy_threshold (float) = Threshold for early stopping based on accuracy.
        logging (bool) = Enables or disables logging during training.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_dim:          int = 1
    output_dim:         int = 1
    learning_rate:      float = 0.1
    accuracy_threshold: float = 0.001
    _logging:           bool = True

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

# LightningModule définition
class LitLinearRegression(pl.LightningModule):

    @override
    def __init__(self, input_dim, output_dim, learning_rate=1e-3, accuracy_threshold=0.5, _logging: bool = False,):
        super(LitLinearRegression, self).__init__()

        self.save_hyperparameters()

        self._logging    = _logging

        # define a simple linear layer
        self.linear = nn.Linear(input_dim, output_dim)

        # define loss criteria
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
            logm.console.log('train_loss', loss)

        return {"loss": loss, "accuracy": acc}

    @override
    def validation_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.criterion(y_hat, y)
        acc = self.calculate_accuracy(y_hat, y)

        if self._logging:
            logm.console.log("val_loss", loss, prog_bar=True)
            logm.console.log("val_acc",  acc,  prog_bar=True)
        
        return {"loss": loss, "accuracy": acc}

    @override
    def test_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.criterion(y_hat, y)
        
        if self._logging:
            logm.console.log('test_loss', loss)

        return loss

    def calculate_accuracy(self, y_hat, y):
        # compute accuracy based on a threshold
        correct = torch.abs(y_hat - y) < self.accuracy_threshold
        accuracy = correct.float().mean()
        return accuracy

    @override
    def configure_optimizers(self):
        return optim.Adam(self.parameters(), lr=self.hparams.learning_rate)

# if __name__ == "__main__":

#     # example
#     input_dim = 1
#     output_dim = 1

#     # Initialize the DataModule
#     data_module = RandomVectorLightningDataModule(num_samples=320, feature_dim=input_dim, batch_size=32)

#     # Initialize the model
#     model = LitLinearRegression(input_dim=input_dim, output_dim=output_dim, _logging = True )

#     # Initialize the Trainer
#     trainer = pl.Trainer(max_epochs=10)

#     # train the model
#     trainer.fit(model, datamodule=data_module)
