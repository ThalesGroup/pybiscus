from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier



class ConfigResultIdentityData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    empty_configuration: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigResultIdentity(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ResultIdentity"
    name:   Literal["resultidentity"]
    config: ConfigResultIdentityData
    model_config = ConfigDict(extra="forbid")



class ResultIdentity(ResultModifier):

    def __init__(self,empty_configuration):
        logm.console.log("ResultIdentity allocated !")
        self.conf = empty_configuration

    def modify(
        self,
        round: int,
        cid: str, 
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        """keep results unchanged"""

        return [w.copy() for w in weights]
