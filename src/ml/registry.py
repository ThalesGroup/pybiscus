from src.ml.data.cifar10.cifar10_datamodule import CifarLitDataModule
from src.ml.models.cnn.lit_cnn import LitCNN

model_registry = {"cifar": LitCNN}
datamodule_registry = {"cifar": CifarLitDataModule}
