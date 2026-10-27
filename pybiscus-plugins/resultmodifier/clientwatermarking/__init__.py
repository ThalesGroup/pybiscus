
from typing import List, Tuple, Type
from pydantic import BaseModel

from clientwatermarking.resultclientwatermarking import ResultClientWatermarking, ConfigResultClientWatermarking
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> List[Tuple[Type[ResultModifier], Type[BaseModel]]]:

    return [
        (ResultClientWatermarking, ConfigResultClientWatermarking),
    ]
