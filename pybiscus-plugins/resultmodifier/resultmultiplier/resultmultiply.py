from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier



class ConfigResultMultiplyData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    factor: float = 1.0
    model_config = ConfigDict(extra="forbid")

class ConfigResultMultiply(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ResultMultiply"
    name:   Literal["result * factor"]
    config: ConfigResultMultiplyData
    model_config = ConfigDict(extra="forbid")



class ResultMultiply(ResultModifier):

    def __init__(self,factor):
        logm.console.log(f"ResultMultiply(factor={factor}) allocated !")
        self.factor = factor

    def modify(
        self,
        cid: str, 
        round: int,
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        """keep results unchanged"""

        return [w.copy() * self.factor for w in weights]
    