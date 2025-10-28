from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier
from pybiscus.flower.utils_server import set_params, get_params


class ConfigResultClientWatermarkingData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigResultClientWatermarking(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ClientWatermarking"
    name:   Literal["client watermarking"]
    config: ConfigResultClientWatermarkingData
    model_config = ConfigDict(extra="forbid")


class ResultClientWatermarking(ResultModifier):

    def __init__(self,empty_configuration):

        self.model = None
        self.fabric = None

        logm.console.log(f"💧 ResultClientWatermarking allocated !")

    def import_context(self):

        if self.model is None:
            from pybiscus.core.pybiscuscontext import pybiscus_context
            self.fabric = pybiscus_context["fabric"]
            self.model = pybiscus_context["model"]


    def modify(
        self,
        cid: str, 
        round: int,
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        self.import_context()

        set_params(self.model, weights)

        #TODO: modify model

        new_weights = get_params(self.model)

        return [w.copy() for w in new_weights]
    