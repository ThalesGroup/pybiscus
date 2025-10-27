
from typing import Dict, List, Tuple
from pydantic import BaseModel

from resultmultiplier.resultmultiply import ResultMultiply, ConfigResultMultiply
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> Tuple[Dict[str, ResultModifier], List[BaseModel]]:

    registry = {
                    "result * factor": ResultMultiply,

                }
    configs  = [
                    ConfigResultMultiply,
                ]

    return registry, configs
