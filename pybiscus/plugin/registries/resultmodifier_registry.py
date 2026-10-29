from pybiscus.plugin.families import family_interface
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- ResultModifier ---

_resultmodifier_loader = RegistryLoader(family_interface("resultmodifier"), True)
_resultmodifier_modules = _resultmodifier_loader.get_submodules_from_path("pybiscus.flower.resultmodifier") 
_resultmodifier_modules += get_plugins_by_category()["resultmodifier"]
_resultmodifier_registry, _resultModifierConfig = _resultmodifier_loader.register_modules( _resultmodifier_modules )

def resultmodifier_registry():
    return _resultmodifier_registry

def ResultModifierConfig():
    return _resultModifierConfig
