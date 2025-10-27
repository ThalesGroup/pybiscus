
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.resultmodifier.basic.resultidentity import ConfigResultIdentity, ResultIdentity
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> Tuple[Dict[str, ResultModifier], List[BaseModel]]:

    registry = {
                    "resultidentity": ResultIdentity,

                }
    configs  = [
                    ConfigResultIdentity,
                ]

    return registry, configs
