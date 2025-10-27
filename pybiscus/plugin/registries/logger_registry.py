from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Logger ---

from pybiscus.interfaces.core.logger import LoggerFactory

_logger_loader = RegistryLoader(LoggerFactory, True)
_logger_modules = _logger_loader.get_submodules_from_path("pybiscus.core.logger") 
_logger_modules += get_plugins_by_category()["logger"]
_logger_registry, _LoggerConfig = _logger_loader.register_modules( _logger_modules )

def logger_registry():
    return _logger_registry

def LoggerConfig():
    return _LoggerConfig
