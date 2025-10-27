from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Data ---

from lightning.pytorch import LightningDataModule

_data_loader = RegistryLoader(LightningDataModule, True)
_data_modules = _data_loader.get_submodules_from_path("pybiscus.ml.data") 
_data_modules += get_plugins_by_category()["data"]
_datamodule_registry, _DataConfig = _data_loader.register_modules( _data_modules )

def datamodule_registry():
    return _datamodule_registry

def DataConfig():
    return _DataConfig
