from typing import ClassVar, List, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict
from pybiscus.core.ensure_filesystem import ensure_file_dir_exists
import pybiscus.core.pybiscus_logger as logm

from pybiscus.interfaces.flower.resultmodifier import ResultModifier
from pybiscus.flower.utils_server import set_params, get_params


class ConfigResultClientWatermarkingData(BaseModel):
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    save_as_cp: bool = True
    model_config = ConfigDict(extra="forbid")

class ConfigResultClientWatermarking(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "ClientWatermarking"
    name:   Literal["client watermarking"]
    config: ConfigResultClientWatermarkingData
    model_config = ConfigDict(extra="forbid")


class ResultClientWatermarking(ResultModifier):

    def __init__(self,save_as_cp):

        self.save_as_cp = save_as_cp

        self.model = None
        self.fabric = None
        self.reporting_path = None

        logm.console.log(f"💧 ResultClientWatermarking allocated !")

    def import_context(self):

        if self.model is None:
            from pybiscus.core.pybiscuscontext import pybiscus_context
            self.fabric = pybiscus_context["fabric"]
            self.model = pybiscus_context["model"]
            self.reporting_path = pybiscus_context["reporting_path"]


    def modify(
        self,
        round: int,
        cid: str, 
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        self.import_context()

        set_params(self.model, weights)

        #TODO: modify model

        if self.save_as_cp:

            checkpoint_client_path = self.reporting_path / f"watermarked_checkpoints/round_{round}/client_{cid}.cp"

            state = {"model": self.model}

            ensure_file_dir_exists(checkpoint_client_path)
            self.fabric.save(checkpoint_client_path, state)
            logm.console.log(f"[fabric] save 💧 watermarked client {cid} checkpoint 💾📍🗄️to : {checkpoint_client_path}")

        new_weights = get_params(self.model)

        return [w.copy() for w in new_weights]
    