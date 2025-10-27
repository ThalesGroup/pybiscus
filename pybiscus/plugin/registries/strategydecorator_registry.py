from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- StrategyDecorator ---

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

_strategydecorator_loader = RegistryLoader(StrategyDecorator, True)
_strategydecorator_modules = _strategydecorator_loader.get_submodules_from_path("pybiscus.flower.strategydecorator") 
_strategydecorator_modules += get_plugins_by_category()["strategydecorator"]
_strategydecorator_registry, _StrategyDecoratorConfig = _strategydecorator_loader.register_modules( _strategydecorator_modules )

def strategydecorator_registry():
    return _strategydecorator_registry

def StrategyDecoratorConfig():
    return _StrategyDecoratorConfig

