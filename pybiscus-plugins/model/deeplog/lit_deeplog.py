from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field
from torchmetrics import Accuracy
from tqdm import tqdm

from deeplog.deeplog import DeepLog

# ------------------------------------------------------------------------------------

class ConfigDeeplog(BaseModel):
    """A Pydantic Model to validate the LitDeeplog config given by the user.

    Attributes
    ----------
    input_shape: int   = number of channels of the input
    mid_shape:   int   = number of channels of the second convolutional layer
    n_classes:   int   = number of classes
    lr:          float = the learning rate
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    input_shape: int   = Field( default=1,     description="input size" )
    mid_shape:   int   = Field( default=64,     description="hidden size" )
    n_layers:   int   = Field( default=2,    description="number of hidden layers" )
    n_classes:   int   = Field( default=33,    description="number of classes" )
    
    lr:          float = Field( default=0.01, description="the learning rate" )
    num_candidates: int = Field( default=9, description="Number of candidates" )
    window_size: int = Field( default=10, description="Window size" )

    model_config = ConfigDict(extra="forbid")

#        --------------------
# edit when the data is ready
class ConfigModel_hdfs(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Deeplog"

    name: Literal["deeplog"]
    config: ConfigDeeplog

    model_config = ConfigDict(extra="forbid")

# ------------------------------------------------------------------------------------

class DeeplogSignature(TypedDict):
    loss: torch.Tensor
    f1score: torch.Tensor
    #accuracy: torch.Tensor

#        --------------------

class LitDeeplog(pl.LightningModule):
    """
    A LightningModule is an abstract class provided by the PyTorch Lightning framework, 
    designed to structure and simplify the development of machine learning models in PyTorch. 
    It encapsulates the entire lifecycle of a model, including training, validation, testing, 
    and inference, while providing additional features for managing configurations, metrics, 
    and callbacks.

    Role of LightningModule

        1) Model Encapsulation:

            Centralizes the model logic, including layers, the forward pass (forward), and loss functions.

        2) Separation of Concerns:

            Separates the model logic from the training logic, enabling better organization and reusability of code.

        3) Code Simplification:

            Reduces code verbosity by automating common tasks such as metric tracking, device management (CPU/GPU), and checkpointing.

    Key Components of a LightningModule

        1) __init__:
            Initializes the model layers and any other necessary components (e.g., loss functions).

        2) forward:
            Defines the forward pass of the model, 
            specifying how data flows through the network to produce an output.

        3) training_step:
            Defines what happens at each training step. 
            This is where you compute the loss and perform backpropagation.

        4) validation_step and test_step:
            Define the validation and test steps, respectively. 
            They are used to evaluate the model's performance on validation or test datasets.

        5) configure_optimizers:
            Configures the optimizers and learning rate schedulers used for training.
    """

    @override
    def __init__( self, input_shape: int, mid_shape: int, n_layers: int, n_classes: int, lr: float, num_candidates: int, window_size: int,_logging: bool = False,):
        super().__init__()
        
        self.save_hyperparameters()

        # memo parameters
        self.input_shape = input_shape
        self.mid_shape   = mid_shape
        self.n_classes   = n_classes
        self.n_layers    = n_layers
        self.lr          = lr
        self._logging    = _logging
        self.num_candidates = num_candidates
        self.window_size = window_size

        self.model       = DeepLog(input_size=self.input_shape, hidden_size=self.mid_shape, num_layers=self.n_layers, num_keys=self.n_classes)
        self.loss        = nn.CrossEntropyLoss()
        self._signature  = DeeplogSignature

    @property
    def signature(self):
        return self._signature

    @override
    def forward(self, data):
        return self.model(data)

    @override
    def training_step(self, batch: torch.Tensor, batch_idx) -> DeeplogSignature:
        log, labels = batch

        outputs = self.forward(log)
        loss    = self.loss(outputs, labels)
        #acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

        if self._logging:
            self.log("train_loss", loss, prog_bar=True)

        return {"loss": loss, "f1score": 0}

    @override
    def validation_step(self, batch: torch.Tensor, batch_idx) -> DeeplogSignature:

        log, targets = batch

        if isinstance(targets,list):
            print('SERVER CASE')
            counts = targets[0]
            labels = targets[1]

            TP = 0
            FP = 0
            FN = 0 
            for line,count,label in tqdm(zip(log,counts,labels)):
                matches = (line == -99).nonzero()
                stop_idx = matches[0][0].item() if matches.numel() > 0 else line.shape[0]
                for i in range(stop_idx - self.window_size):
                    seq0 = line[i:i + self.window_size]
                    next_event = line[i + self.window_size]


                    seq0 = torch.tensor(seq0, dtype=torch.float).clone().detach().view(
                        -1, self.window_size, self.input_shape)
                    next_event = torch.tensor(next_event).clone().detach().view(-1)
                    output = self.forward(seq0)
              
                    predicted = torch.argsort(output,
                                              1)[0][-self.num_candidates:]

                    if next_event not in predicted: 
                        if label.item() == 1:
                            TP += count.item()
                            break
                        else:
                            FP += count.item()
                            break

            counts_abnormal=[ count.item() for count,label in zip(counts,labels) if label.item()==1]
            FN = sum(counts_abnormal) - TP
            P = 100 * TP / (TP + FP)
            R = 100 * TP / (TP + FN)
            F1 = 2 * P * R / (P + R)
            print('false positive (FP): {}, false negative (FN): {}, Precision: {:.3f}%, Recall: {:.3f}%, F1-measure: {:.3f}%'
                .format(FP, FN, P, R, F1))  

            if self._logging:
                self.log("f1score", F1, prog_bar=True)           

            return {"loss": 0, "f1score": F1}
        
        else: 
            print('CLIENT CASE')
            outputs = self.forward(log)
            loss    = self.loss(outputs, targets)
            print(loss)
            #acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

            if self._logging:
                self.log("val_loss", loss, prog_bar=True)
                #self.log("val_acc",  acc,  prog_bar=True)

            return {"loss": loss, "f1score": 0}
 

         
    #@override
    def test_step(self, batch: torch.Tensor, batch_idx) -> torch.Tensor:

        log, targets = batch

        if isinstance(targets, list):
            print('SERVER CASE')
            counts = targets[0]
            labels = targets[1]

            TP = 0
            FP = 0
            FN = 0
            for line, count, label in tqdm(zip(log, counts, labels)):
                matches = (line == -99).nonzero()
                stop_idx = matches[0][0].item() if matches.numel() > 0 else line.shape[0]
                for i in range(stop_idx - self.window_size):
                    seq0 = line[i:i + self.window_size]
                    next_event = line[i + self.window_size]

                    seq0 = torch.tensor(seq0, dtype=torch.float).clone().detach().view(
                        -1, self.window_size, self.input_shape)
                    next_event = torch.tensor(next_event).clone().detach().view(-1)
                    output = self.forward(seq0)

                    predicted = torch.argsort(output,
                                              1)[0][-self.num_candidates:]

                    if next_event not in predicted:
                        if label.item() == 1:
                            TP += count.item()
                            break
                        else:
                            FP += count.item()
                            break

            counts_abnormal = [count.item() for count, label in zip(counts, labels) if label.item() == 1]
            FN = sum(counts_abnormal) - TP
            P = 100 * TP / (TP + FP)
            R = 100 * TP / (TP + FN)
            F1 = 2 * P * R / (P + R)
            print(
                'false positive (FP): {}, false negative (FN): {}, Precision: {:.3f}%, Recall: {:.3f}%, F1-measure: {:.3f}%'
                .format(FP, FN, P, R, F1))

            if self._logging:
                self.log("f1score", F1, prog_bar=True)

            return {"loss": 0, "f1score": F1}

        else:
            print('CLIENT CASE')
            outputs = self.forward(log)
            loss = self.loss(outputs, targets)
            print(loss)
            # acc     = self.accuracy(torch.max(outputs.data, 1)[1], labels)

            if self._logging:
                self.log("val_loss", loss, prog_bar=True)
                # self.log("val_acc",  acc,  prog_bar=True)

            return {"loss": loss, "f1score": 0}

    @override
    def configure_optimizers(self) -> None:
        return torch.optim.Adam(self.parameters(), lr=self.lr)

