
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.resultmodifier.basicresultmodifiers.resultidentity import ConfigResultIdentity, ResultIdentity
from pybiscus.flower.resultmodifier.basicresultmodifiers.resultmultiply import ConfigResultMultiply, ResultMultiply
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> Tuple[Dict[str, ResultModifier], List[BaseModel]]:

    registry = {
                    "resultidentity": ResultIdentity,
                    "result * factor": ResultMultiply,

                }
    configs  = [
                    ConfigResultIdentity,
                    ConfigResultMultiply,
                ]

    return registry, configs
