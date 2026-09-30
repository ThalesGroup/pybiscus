
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.clientfactory import ClientFactory
from byzantine.byzantineclient import ByzantineClientFactory, ConfigByzantineClient

def get_modules_and_configs() -> Tuple[Dict[str, ClientFactory], List[BaseModel]]:

    registry = {"byzantine": ByzantineClientFactory,}
    configs  = [ConfigByzantineClient,]

    return registry, configs
