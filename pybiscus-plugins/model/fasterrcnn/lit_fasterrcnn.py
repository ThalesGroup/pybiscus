from typing import override, Literal, TypedDict, ClassVar

import lightning.pytorch as pl
import torch
import torch.nn as nn
from pydantic import BaseModel, ConfigDict, Field
from torchmetrics import Accuracy
from tqdm import tqdm
from torch.optim.lr_scheduler import MultiStepLR

from torchmetrics.detection.mean_ap import MeanAveragePrecision
from torchmetrics.classification.accuracy import Accuracy, MulticlassAccuracy
from torchmetrics.classification.confusion_matrix import (
    MulticlassConfusionMatrix,
    BinaryConfusionMatrix,
)
from fasterrcnn.fasterrcnn import FasterRCNN, DectionProbability, FalseAlarmProbability
import numpy as np
import pandas as pd

# ------------------------------------------------------------------------------------

class ConfigFasterRCNN(BaseModel):
    """A Pydantic Model to validate the LitDeeplog config given by the user.

    Attributes
    ----------
    trainable_backbone_layers: int   = Number of backbone layers to freeze (0 to 5)
    pretrained: bool = True to use pretrained weights on COCO
    variant:   str   = V1 or V2
    num_classes:   int   = number of classes

    learning_rate : float
    lr_milestones : list[int] Epochs auxquels diviser le LR par lr_gamma.
    lr_gamma : float
    label_dict : dict | None
        Mapping index → nom de classe (for logging).
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    trainable_backbone_layers: int   = Field( default=5,     description="Number of backbone layers to freeze (0 to 5)" )
    pretrained:   bool   = Field( default=True,     description="True to use pretrained weights on COCO" )
    variant:   str   = Field( default="v2",    description="V1 or V2" )
    num_classes:   int   = Field( default=10,    description="number of classes" )


    model_config = ConfigDict(extra="forbid")

#        --------------------
# edit when the data is ready
class ConfigModel_FasterRCNN(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FasterRCNN"

    name: Literal["fasterrcnn"]
    config: FasterRCNN

    model_config = ConfigDict(extra="forbid")

# ------------------------------------------------------------------------------------

class FasterRCNNSignature(TypedDict):
    loss: torch.Tensor
    #accuracy: torch.Tensor

#        --------------------

class LitFasterRCNN(pl.LightningModule):
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
    def __init__( self, trainable_backbone_layers: int, pretrained: bool, variant: str, num_classes: int, label_binary_dict):
        super().__init__()
        
        self.save_hyperparameters()

        # memo parameters
 
        self.trainable_backbone_layers =  trainable_backbone_layers
        self.pretrained = pretrained
        self.variant =  variant
        self.num_classes = self.num_classes
        self.model       = FasterRCNN(
            num_classes=self.num_classes, 
            variant=self.variant, 
            pretrained=self.pretrained, 
            num_classes=self.num_classes)
        self._signature  = FasterRCNNSignature


        self.label_binary_dict = label_binary_dict
        if len(set(self.label_binary_dict.values())) != 2:
            raise ValueError(
                f"Label Binary dict should map to only 2 values {self.label_binary_dict.values()}"
            )
        if not (1 in self.label_binary_dict.values()):
            raise ValueError(
                f"Label Binary dict should map should contains 1 as value for threats {self.label_binary_dict.values()}"
            )

        
        self.detection_metrics = MeanAveragePrecision(
            box_format="xyxy", iou_type="bbox"
        )
        self.confusion_matrices = {
            "CM": MulticlassConfusionMatrix(num_classes=num_classes),
            "CM_bin": BinaryConfusionMatrix(),
        }
        self.classification_metrics = {
            "MacroAcc": MulticlassAccuracy(num_classes=num_classes, average="macro"),
            "FalseAlarmProba": FalseAlarmProbability(label_binary_dict),
            "DetectionProba": DectionProbability(label_binary_dict),
        }
        self.test_ok_score = []
        self.test_nok_score = []
        self.label0_pred1 = []
        self.label0_pred0 = []
        self.label1_pred1 = []
        self.label1_pred0 = []

    @property
    def signature(self):
        return self._signature

    @override
    def forward(self, images, targets=None):
        return self.model(images, targets)

    @override
    def training_step(self, batch: torch.Tensor, batch_idx) -> FasterRCNNSignature:
        log, labels = batch

        self.model.train()
        images, targets = batch
        loss_dict = self.model(images, targets)
        self.model.eval()
        output = self.model(images)
        self._update_metrics(output, targets, mode="train")
        self.model.train()
        sum_losses = self._log_losses(loss_dict, "train_loss", batch_size=len(images))

        return {"loss": sum_losses}

    @override
    def validation_step(self, batch: torch.Tensor, batch_idx) -> FasterRCNNSignature:

        images, targets = batch
        self.model.train()
        loss_dict = self.model(images, targets)
        sum_losses = self._log_losses(loss_dict, "val_loss", batch_size=len(images))
        self.model.eval()
        output = self.model(images)
        self._update_metrics(output, targets, mode="val")
        self.model.train()

        return {"loss": sum_losses}

         
    #@override
    def test_step(self, batch: torch.Tensor, batch_idx) -> torch.Tensor:

        images, targets = batch
        self.model.eval()
        output = self.model(images, targets)

        self._update_metrics(output, targets,  mode="val")
        return output
    
    def on_validation_epoch_end(self):
        self._log_metrics("val", "val")
        return super().on_validation_epoch_end()

    def on_validation_start(self):
        self._log_metrics("train", "train")
        return super().on_validation_start()

    def on_test_end(self):
        self._log_metrics("test", verbose=True)
        print(map, self.detection_metrics.compute())
        for name, metric in self.classification_metrics.items():
            print(name, metric.compute())
        for name, metric in self.confusion_matrices.items():
            print(name, metric.compute())
        print(self.label0_pred0)
        print(self.label0_pred1)
        print(self.label1_pred0)
        print(self.label1_pred1)
        self.label0_pred0 = np.array(self.label0_pred0)
        self.label0_pred1 = np.array(self.label0_pred1)
        self.label1_pred0 = np.array(self.label1_pred0)
        self.label1_pred1 = np.array(self.label1_pred1)
        df_data = []
        for th in range(100):
            th/=100
            Nb_Flase_alarm = sum(np.where(self.label0_pred1>=th, 1,0))
            Nb_truth_0 = (len(self.label0_pred0) + len((self.label0_pred1)))
            False_alarm_Proba = Nb_Flase_alarm / Nb_truth_0
            Nb_Detection = sum(np.where(self.label1_pred1>=th, 1,0))
            Nb_truth_0 = (len(self.label1_pred0) + len((self.label1_pred1)))
            Detection_Proba = Nb_Detection / Nb_truth_0
            df_data.append({
                "th": th,
                "Nb_Flase_alarm" : Nb_Flase_alarm,
                "Nb_truth_0" : Nb_truth_0,
                "False_alarm_Proba" : False_alarm_Proba,
                "Nb_Detection" : Nb_Detection,
                "Nb_truth_0" : Nb_truth_0,
                "Detection_Proba" : Detection_Proba,
            })
        df = pd.DataFrame.from_records(df_data)
        print(df)
        # df.to_csv(f"{self.output_img_folder}/seuils.csv", index=False)
        # fig = px.scatter(df, x="False_alarm_Proba", y="Detection_Proba", hover_data="th", title="Probabilité de détections et de fausses alarmes sur l'ensemble de validation en fonction du seuil sur le score")
        # fig.add_hline(y=0.9,line_dash="dash")
        # fig.add_vline(x=0.01,line_dash="dash")
        # fig.write_image(f"{self.output_img_folder}/seuils.png")

        print("test_ok_score", self.test_ok_score)
        print("************")
        print("test_nok_score", self.test_nok_score)
        ok_score = np.array(self.test_ok_score)
        nok_score = np.array(self.test_nok_score)
        print("test_ok_score", len(ok_score), np.max(ok_score), np.min(ok_score), np.mean(ok_score), np.median(ok_score))
        no_preds = np.sum(np.where(nok_score==-1))
        print("number_no_preds", no_preds, len(nok_score))
        no_preds = nok_score[np.where(nok_score==-1)]
        print("number_no_preds", -np.sum(no_preds))
        nok_score = nok_score[np.where(nok_score!=-1)]
        print("test_nok_score", len(nok_score), np.max(nok_score), np.min(nok_score), np.mean(nok_score), np.median(nok_score))

        return super().on_test_end()
        
    def _update_metrics(self, output, targets, mode="val", verbose=False):
        labels_pred = []
        labels_target = []
        for o, t in zip(output, targets):
            if len(o["scores"]) > 1:
                idx = torch.argmax(o["scores"])
                labels_pred.append(int(o["labels"][idx]))
            elif len(o["scores"]) == 1:
                labels_pred.append(int(o["labels"][0]))
            else:
                labels_pred.append(0)
            labels_target.append(int(t["labels"]))
        labels_pred = torch.Tensor(labels_pred).to(int)
        labels_target = torch.Tensor(labels_target).to(int)
        if mode == "val":
            self.detection_metrics.update(output, targets)
        if verbose:
            print("targets and pred", labels_target, labels_pred)
        for metric in self.classification_metrics.values():
            metric.update(labels_pred, labels_target)
            if verbose:
                print(metric.compute())
        for name, metric in self.confusion_matrices.items():
            if name[-3:] == "bin":
                metric.update(
                    torch.Tensor(
                        [self.label_binary_dict[p] for p in labels_pred.tolist()]
                    ),
                    torch.Tensor(
                        [self.label_binary_dict[p] for p in labels_target.tolist()]
                    ),
                )
            else:
                metric.update(labels_pred, labels_target)
            if verbose:
                print(name, metric.compute())

    def _log_metrics(self, prefix, mode="val", verbose=False):
        for name in self.confusion_matrices.keys():
            conf_mat = self.confusion_matrices[name].compute()
            if verbose:
                print(name, conf_mat)
            self.logger.experiment.add_figure(
                f"{prefix}/{name}",
                self._plot_CM(conf_mat),
                global_step=self.current_epoch,
            )
            self.confusion_matrices[name].reset()
        for name in self.classification_metrics.keys():
            acc = self.classification_metrics[name].compute()
            if verbose:
                print(name, acc)
            self.logger.experiment.add_scalar(
                f"{prefix}/{name}", acc, global_step=self.current_epoch
            )
            self.classification_metrics[name].reset()
        if mode == "val":
            map = self.detection_metrics.compute()
            for k, v in map.items():
                if (len(v.shape) >= 1) and (v.shape[0] == 1):
                    self.logger.experiment.add_scalar(
                        f"{prefix}/{k}", v, global_step=self.current_epoch
                    )
            self.detection_metrics.reset()

    def _log_losses(self, loss_dict, prefix, batch_size):
        losses = sum(loss for loss in loss_dict.values())
        self.log(f"{prefix}/global", losses, batch_size=batch_size)
        for loss_name, value in loss_dict.items():
            self.log(f"{prefix}/{loss_name}", value, batch_size=batch_size)
        return losses

    @override
    def configure_optimizers(self):
        optimizer = torch.optim.SGD(
            self.parameters(),
            lr=0.005,  # Common starting LR for Faster R-CNN
            momentum=0.9,
            weight_decay=0.0005,
        )
        scheduler = MultiStepLR(
            optimizer,
            milestones=[8, 11],  # Adjust based on your total epochs
            gamma=0.1,
        )
        return [optimizer], [scheduler]


