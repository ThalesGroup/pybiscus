
from collections import defaultdict
from pybiscus.core.metricslogger.interface.metricsloggerfactory import MetricsLoggerFactory
from pybiscus.core.pluginmanager import get_plugins_by_category
from pybiscus.core.registryloader import RegistryLoader

from lightning.pytorch import LightningDataModule, LightningModule

from pybiscus.flower.strategy.interface.fabricstrategyfactory import FabricStrategyFactory


try:
    plugins_by_category = get_plugins_by_category()
except Exception as e:
    print(f"❌ Can not load pybiscus plugins {e}")
    plugins_by_category = defaultdict(list)

#### --- Data ---

_data_loader = RegistryLoader(LightningDataModule, True)
_data_modules = _data_loader.get_submodules_from_path("pybiscus.ml.data") 
_data_modules += plugins_by_category["data"]
_datamodule_registry, _DataConfig = _data_loader.register_modules( _data_modules )

def datamodule_registry():
    return _datamodule_registry

def DataConfig():
    return _DataConfig

#### --- Models ---

_model_loader = RegistryLoader(LightningModule, True)
_model_modules = _data_loader.get_submodules_from_path("pybiscus.ml.models") 
_model_modules += plugins_by_category["model"]
_model_registry, _ModelConfig = _model_loader.register_modules( _model_modules )

def model_registry():
    return _model_registry

def ModelConfig():
    return _ModelConfig

#### --- Strategy ---

_strategy_loader = RegistryLoader(FabricStrategyFactory, True)
_strategy_modules = _data_loader.get_submodules_from_path("pybiscus.flower.strategy") 
_strategy_modules += plugins_by_category["strategy"]
_strategy_registry, _StrategyConfig = _strategy_loader.register_modules( _strategy_modules )

def strategy_registry():
    return _strategy_registry

def StrategyConfig():
    return _StrategyConfig

#### --- Logger ---

_metricslogger_loader = RegistryLoader(MetricsLoggerFactory, True)
_metricslogger_modules = _metricslogger_loader.get_submodules_from_path("pybiscus.core.metricslogger") 
_metricslogger_modules += plugins_by_category["metricslogger"]
_metricslogger_registry, _MetricsLoggerConfig = _metricslogger_loader.register_modules( _metricslogger_modules )

def metricslogger_registry():
    return _metricslogger_registry

def MetricsLoggerConfig():
    return _MetricsLoggerConfig

if __name__ == "__main__":
    print(f'MetricsLogger plugins : {plugins_by_category["metricslogger"]} {_metricslogger_modules}')
    print(f'Data plugins : {plugins_by_category["data"]} {_data_modules}')
    print(f'Model plugins : {plugins_by_category["model"]} {_model_modules}')
    print(f'Strategy plugins : {plugins_by_category["strategy"]} {_strategy_modules }')
