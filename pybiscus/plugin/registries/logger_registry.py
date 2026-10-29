from pybiscus.plugin.families import family_interface
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Logger ---

_logger_loader = RegistryLoader(family_interface("logger"), True)
_logger_modules = _logger_loader.get_submodules_from_path("pybiscus.core.logger") 
_logger_modules += get_plugins_by_category()["logger"]
_logger_registry, _LoggerConfig = _logger_loader.register_modules( _logger_modules )

def logger_registry():
    return _logger_registry

def LoggerConfig():
    return _LoggerConfig
