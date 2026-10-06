
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.clientfactory import ClientFactory
from relayclient.relayclientfactory import RelayClientFactory, ConfigFlowerRelayClient

def get_modules_and_configs() -> Tuple[Dict[str, ClientFactory], List[BaseModel]]:

    registry = {"relay": RelayClientFactory,}
    configs  = [ConfigFlowerRelayClient,]

    return registry, configs
