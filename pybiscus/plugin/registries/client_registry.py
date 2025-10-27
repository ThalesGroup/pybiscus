from pybiscus.plugin.registryloader import RegistryLoader
from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

#### --- Client ---

from pybiscus.interfaces.flower.clientfactory import ClientFactory

_client_loader = RegistryLoader(ClientFactory, True)
_client_modules = _client_loader.get_submodules_from_path("pybiscus.flower_fabric.client") 
_client_modules += get_plugins_by_category()["client"]
_client_registry, _ClientConfig = _client_loader.register_modules( _client_modules )

def client_registry():
    return _client_registry

def ClientConfig():
    return _ClientConfig
