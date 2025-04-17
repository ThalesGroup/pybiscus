
from pybiscus.core.registryloader import RegistryLoader

from lightning.pytorch import LightningDataModule, LightningModule

#### --- Data ---

data_loader = RegistryLoader(LightningDataModule, True)
datamodule_registry, DataConfig = data_loader.register_from_path("pybiscus.ml.data")

#### --- Models ---

model_loader = RegistryLoader(LightningModule, True)
model_registry, ModelConfig = model_loader.register_from_path("pybiscus.ml.models")

#### --- Strategy ---

from flwr.server.strategy import Strategy

strategy_loader = RegistryLoader(Strategy, True)
strategy_registry, StrategyConfig = strategy_loader.register_from_path("pybiscus.flower.strategy")
