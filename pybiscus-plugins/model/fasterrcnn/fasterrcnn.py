7

import torch
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection import (
    fasterrcnn_resnet50_fpn,
    FasterRCNN_ResNet50_FPN_Weights,
    fasterrcnn_resnet50_fpn_v2,
    FasterRCNN_ResNet50_FPN_V2_Weights,
)
import torch.nn as nn
from torchmetrics import Metric

class FasterRCNN(nn.Module):
    def __init__(self,     
                 num_classes: int,
                 *,
                 variant: str = "v1",
                 pretrained: bool = True,
                 trainable_backbone_layers: int = 5) -> nn.Module:
        """
        Instancie un Faster R-CNN ResNet50-FPN avec un predictor adapté.

        Parameters
        ----------
        num_classes : int
            Nombre de classes (incluant le fond, classe 0).
        variant : str
            "v1" (FasterRCNN_ResNet50_FPN) ou "v2" (FasterRCNN_ResNet50_FPN_V2).
        pretrained : bool
            Charger les poids COCO pré-entraînés.
        trainable_backbone_layers : int
            Nombre de couches backbone à dégeler (0 à 5).

        Returns
        -------
        nn.Module
            Modèle prêt pour l'entraînement.
        """
        if variant == "v2":
            weights = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT if pretrained else None
            model = fasterrcnn_resnet50_fpn_v2(
                weights=weights,
                trainable_backbone_layers=trainable_backbone_layers,
            )
        else:
            weights = FasterRCNN_ResNet50_FPN_Weights.DEFAULT if pretrained else None
            model = fasterrcnn_resnet50_fpn(
                weights=weights,
                trainable_backbone_layers=trainable_backbone_layers,
            )

        # Remplacer le predictor par défaut par un predictor adapté à num_classes
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

        return model
    

class DectionProbability(Metric):
    """
    La probabilité de détection d’une menace potentielle (classe 02 ou classe 99) doit être supérieure à 90% (dans la mesure où le rapport signal a bruit est suffisant, ce que l’on supposera ici)
    args:
        - label_binary_dict = Dictionnary that associate to a label the fact of being a threat. Threat is 1.
    """

    def __init__(self, label_binary_dict, **kwargs):
        super().__init__(**kwargs)
        self.add_state("correct", default=torch.tensor(0), dist_reduce_fx="sum")
        self.add_state("total", default=torch.tensor(0), dist_reduce_fx="sum")
        self.label_binary_dict = label_binary_dict
        if len(set(self.label_binary_dict.values())) != 2:
            raise ValueError(
                f"Label Binary dict should map to only 2 values {self.label_binary_dict.values()}"
            )
        if not (1 in self.label_binary_dict.values()):
            raise ValueError(
                f"Label Binary dict should map should contains 1 as value for threats {self.label_binary_dict.values()}"
            )

    def _tobinary(self, preds):
        return [self.label_binary_dict[p] for p in preds]

    def _to_list(self, t):
        if t.__class__.__module__ == "torch":
            return t.tolist()
        return t

    def _input_format(self, preds, target):
        return self._to_list(preds), self._to_list(target)

    def update(self, preds: torch.Tensor, target: torch.Tensor) -> None:
        preds, target = self._input_format(preds, target)
        if len(preds) != len(target):
            raise ValueError("preds and target must have the same shape")

        preds_bin = torch.Tensor(self._tobinary(preds))
        target_bin = torch.Tensor(self._tobinary(target))

        idx_threat = target_bin == 1

        self.correct += torch.sum(preds_bin[idx_threat] == target_bin[idx_threat])
        self.total += target_bin[idx_threat].numel()

    def compute(self) -> torch.Tensor:
        return self.correct.float() / self.total


class FalseAlarmProbability(Metric):
    """
    La probabilité de fausse alarme qui consiste à décider (classe 02 ou classe 99) alors que la classe est (00 ou 01) doit être inférieure à 1%.
    args:
        - label_binary_dict = Dictionnary that associate to a label the fact of being a threat. Threat is 1.
    """

    def __init__(self, label_binary_dict, **kwargs):
        super().__init__(**kwargs)
        self.add_state("error", default=torch.tensor(0), dist_reduce_fx="sum")
        self.add_state("total", default=torch.tensor(0), dist_reduce_fx="sum")
        self.label_binary_dict = label_binary_dict
        if len(set(self.label_binary_dict.values())) != 2:
            raise ValueError(
                f"Label Binary dict should map to only 2 values {self.label_binary_dict.values()}"
            )
        if not (1 in self.label_binary_dict.values()):
            raise ValueError(
                f"Label Binary dict should map should contains 1 as value for threats {self.label_binary_dict.values()}"
            )

    def _tobinary(self, preds):
        return [self.label_binary_dict[p] for p in preds]

    def _to_list(self, t):
        if t.__class__.__module__ == "torch":
            return t.tolist()
        return t

    def _input_format(self, preds, target):
        return self._to_list(preds), self._to_list(target)

    def update(self, preds: torch.Tensor, target: torch.Tensor) -> None:
        preds, target = self._input_format(preds, target)
        if len(preds) != len(target):
            raise ValueError("preds and target must have the same shape")
        preds_bin = torch.Tensor(self._tobinary(preds))
        target_bin = torch.Tensor(self._tobinary(target))

        idx_nothreat = target_bin != 1

        self.error += torch.sum(preds_bin[idx_nothreat] != target_bin[idx_nothreat])
        self.total += target_bin[idx_nothreat].numel()

    def compute(self) -> torch.Tensor:
        return self.error.float() / self.total

