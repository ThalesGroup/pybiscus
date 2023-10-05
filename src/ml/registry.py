from src.ml.data.cifar10_datamodule import CifarLitDataModule
from src.ml.data.cifar10_dataset import load_data
from src.ml.models.lit_cnn import LitCNN

data_registry = {"cifar": load_data}
model_registry = {"cifar": LitCNN}
datamodule_registry = {"cifar": CifarLitDataModule}
