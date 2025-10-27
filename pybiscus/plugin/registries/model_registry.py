from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Models ---

from lightning.pytorch import LightningModule

_model_loader = RegistryLoader(LightningModule, True)
_model_modules = _model_loader.get_submodules_from_path("pybiscus.ml.models") 
_model_modules += get_plugins_by_category()["model"]
_model_registry, _ModelConfig = _model_loader.register_modules( _model_modules )

def model_registry():
    return _model_registry

def ModelConfig():
    return _ModelConfig

