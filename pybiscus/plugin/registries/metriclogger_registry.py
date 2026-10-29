from pybiscus.plugin.families import family_interface
from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Metric Logger ---

_metricslogger_loader = RegistryLoader(family_interface("metricslogger"), True)
_metricslogger_modules = _metricslogger_loader.get_submodules_from_path("pybiscus.core.metricslogger") 
_metricslogger_modules += get_plugins_by_category()["metricslogger"]
_metricslogger_registry, _MetricsLoggerConfig = _metricslogger_loader.register_modules( _metricslogger_modules )

def metricslogger_registry():
    return _metricslogger_registry

def MetricsLoggerConfig():
    return _MetricsLoggerConfig
