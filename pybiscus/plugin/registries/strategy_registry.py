from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Strategy ---

from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

_strategy_loader = RegistryLoader(FabricStrategyFactory, True)
_strategy_modules = _strategy_loader.get_submodules_from_path("pybiscus.flower.strategy") 
_strategy_modules += get_plugins_by_category()["strategy"]
_strategy_registry, _StrategyConfig = _strategy_loader.register_modules( _strategy_modules )

def strategy_registry():
    return _strategy_registry

def StrategyConfig():
    return _StrategyConfig

