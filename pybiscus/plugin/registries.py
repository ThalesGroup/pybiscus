
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

plugins_by_category = get_plugins_by_category()

#### --- Data ---

from lightning.pytorch import LightningDataModule

_data_loader = RegistryLoader(LightningDataModule, True)
_data_modules = _data_loader.get_submodules_from_path("pybiscus.ml.data") 
_data_modules += plugins_by_category["data"]
_datamodule_registry, _DataConfig = _data_loader.register_modules( _data_modules )

def datamodule_registry():
    return _datamodule_registry

def DataConfig():
    return _DataConfig

#### --- Models ---

from lightning.pytorch import LightningModule

_model_loader = RegistryLoader(LightningModule, True)
_model_modules = _data_loader.get_submodules_from_path("pybiscus.ml.models") 
_model_modules += plugins_by_category["model"]
_model_registry, _ModelConfig = _model_loader.register_modules( _model_modules )

def model_registry():
    return _model_registry

def ModelConfig():
    return _ModelConfig

#### --- Strategy ---

from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

_strategy_loader = RegistryLoader(FabricStrategyFactory, True)
_strategy_modules = _data_loader.get_submodules_from_path("pybiscus.flower.strategy") 
_strategy_modules += plugins_by_category["strategy"]
_strategy_registry, _StrategyConfig = _strategy_loader.register_modules( _strategy_modules )

def strategy_registry():
    return _strategy_registry

def StrategyConfig():
    return _StrategyConfig

#### --- StrategyDecorator ---

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

_strategydecorator_loader = RegistryLoader(StrategyDecorator, True)
_strategydecorator_modules = _data_loader.get_submodules_from_path("pybiscus.flower.strategydecorator") 
_strategydecorator_modules += plugins_by_category["strategydecorator"]
_strategydecorator_registry, _StrategyDecoratorConfig = _strategydecorator_loader.register_modules( _strategydecorator_modules )

def strategydecorator_registry():
    return _strategydecorator_registry

def StrategyDecoratorConfig():
    return _StrategyDecoratorConfig

#### --- Metric Logger ---

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory

_metricslogger_loader = RegistryLoader(MetricsLoggerFactory, True)
_metricslogger_modules = _metricslogger_loader.get_submodules_from_path("pybiscus.core.metricslogger") 
_metricslogger_modules += plugins_by_category["metricslogger"]
_metricslogger_registry, _MetricsLoggerConfig = _metricslogger_loader.register_modules( _metricslogger_modules )

def metricslogger_registry():
    return _metricslogger_registry

def MetricsLoggerConfig():
    return _MetricsLoggerConfig

#### --- Logger ---

from pybiscus.interfaces.core.logger import LoggerFactory

_logger_loader = RegistryLoader(LoggerFactory, True)
_logger_modules = _logger_loader.get_submodules_from_path("pybiscus.core.logger") 
_logger_modules += plugins_by_category["logger"]
_logger_registry, _LoggerConfig = _logger_loader.register_modules( _logger_modules )

def logger_registry():
    return _logger_registry

def LoggerConfig():
    return _LoggerConfig

#### --- Client ---

from pybiscus.interfaces.flower.clientfactory import ClientFactory

_client_loader = RegistryLoader(ClientFactory, True)
_client_modules = _data_loader.get_submodules_from_path("pybiscus.flower_fabric.client") 
_client_modules += plugins_by_category["client"]
_client_registry, _ClientConfig = _client_loader.register_modules( _client_modules )

def client_registry():
    return _client_registry

def ClientConfig():
    return _ClientConfig


if __name__ == "__main__":
    print(f'Logger plugins : {plugins_by_category["logger"]} {_logger_modules}')
    print(f'MetricsLogger plugins : {plugins_by_category["metricslogger"]} {_metricslogger_modules}')
    print(f'Data plugins : {plugins_by_category["data"]} {_data_modules}')
    print(f'Model plugins : {plugins_by_category["model"]} {_model_modules}')
    print(f'Strategy plugins : {plugins_by_category["strategy"]} {_strategy_modules }')
    print(f'StrategyDecorator plugins : {plugins_by_category["strategydecorator"]} {_strategydecorator_modules }')
    print(f'Client plugins : {plugins_by_category["client"]} {_client_modules }')

    from pybiscus.plugin.registries2 import _flowerfitresultsaggregator_modules
    print(f'FlowerFitResultsAggregator plugins : {plugins_by_category["flowerfitresultsaggregator"]} {_flowerfitresultsaggregator_modules }')
