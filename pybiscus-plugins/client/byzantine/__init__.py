
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.clientfactory import ClientFactory
from byzantine.byzantineclient import ByzantineClientFactory, ConfigByzantineClient

def get_modules_and_configs() -> List[Tuple[Type[ClientFactory], Type[BaseModel]]]:

    return [
        (ByzantineClientFactory, ConfigByzantineClient),
    ]
