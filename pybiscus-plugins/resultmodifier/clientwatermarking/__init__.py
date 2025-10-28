
from typing import Dict, List, Tuple
from pydantic import BaseModel

from clientwatermarking.resultclientwatermarking import ResultClientWatermarking, ConfigResultClientWatermarking
from pybiscus.interfaces.flower.resultmodifier import ResultModifier

def get_modules_and_configs() -> Tuple[Dict[str, ResultModifier], List[BaseModel]]:

    registry = {
                    "client watermarking": ResultClientWatermarking,

                }
    configs  = [
                    ConfigResultClientWatermarking,
                ]

    return registry, configs
