
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.clientfactory import ClientFactory
from relayclient.relayclientfactory import RelayClientFactory, ConfigFlowerRelayClient

def get_modules_and_configs() -> List[Tuple[Type[ClientFactory], Type[BaseModel]]]:

    return [
        (RelayClientFactory, ConfigFlowerRelayClient),
    ]
