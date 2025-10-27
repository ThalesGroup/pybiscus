from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Metric Logger ---

from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory

_metricslogger_loader = RegistryLoader(MetricsLoggerFactory, True)
_metricslogger_modules = _metricslogger_loader.get_submodules_from_path("pybiscus.core.metricslogger") 
_metricslogger_modules += get_plugins_by_category()["metricslogger"]
_metricslogger_registry, _MetricsLoggerConfig = _metricslogger_loader.register_modules( _metricslogger_modules )

def metricslogger_registry():
    return _metricslogger_registry

def MetricsLoggerConfig():
    return _MetricsLoggerConfig
