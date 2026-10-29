from pybiscus.plugin.families import family_interface
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- FlowerFitResultsAggregator ---

_flowerfitresultsaggregator_loader = RegistryLoader(family_interface("flowerfitresultsaggregator"), True)
_flowerfitresultsaggregator_modules = _flowerfitresultsaggregator_loader.get_submodules_from_path("pybiscus.flower.flowerfitresultsaggregator") 
_flowerfitresultsaggregator_modules += get_plugins_by_category()["flowerfitresultsaggregator"]
_flowerfitresultsaggregator_registry, _FlowerFitResultsAggregatorConfig = _flowerfitresultsaggregator_loader.register_modules( _flowerfitresultsaggregator_modules )

def flowerfitresultsaggregator_registry():
    return _flowerfitresultsaggregator_registry

def FlowerFitResultsAggregatorConfig():
    return _FlowerFitResultsAggregatorConfig
