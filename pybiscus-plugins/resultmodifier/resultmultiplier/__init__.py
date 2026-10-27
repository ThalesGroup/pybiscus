
from typing import List, Tuple, Type
from pydantic import BaseModel

from resultmultiplier.resultmultiply import ResultMultiply, ConfigResultMultiply
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> List[Tuple[Type[ResultModifier], Type[BaseModel]]]:

    return [
        (ResultMultiply, ConfigResultMultiply),
    ]
