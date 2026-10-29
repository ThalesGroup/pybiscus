from pybiscus.plugin.families import family_interface
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- StoppingCriterion ---

_stoppingcriterion_loader = RegistryLoader(family_interface("stoppingcriterion"), True)
_stoppingcriterion_modules = _stoppingcriterion_loader.get_submodules_from_path("pybiscus.flower.stoppingcriterion")
_stoppingcriterion_modules += get_plugins_by_category()["stoppingcriterion"]
_stoppingcriterion_registry, _StoppingCriterionConfig = _stoppingcriterion_loader.register_modules( _stoppingcriterion_modules )

def stoppingcriterion_registry():
    return _stoppingcriterion_registry

def StoppingCriterionConfig():
    return _StoppingCriterionConfig
