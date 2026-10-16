from typing import ClassVar, Literal
import flwr as fl

from flwr.server.strategy import Strategy

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.core.reportingoutputs import CID, ROUND, TAG, TaggedReportingOutputs, output_file
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigSaveClientsFitResStrategyDecoratorData(TaggedReportingOutputs):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = Field(default="rounds", description='subdirectory of the reporting directory, one round_<n> directory per round inside')
    client_fitres_parameters_file_prefix: str = Field(default="client_fitres_parameters", description='prefix of the files of the weights each client sent back')

    model_config = ConfigDict(extra="forbid")

    def reporting_outputs(self):
        return {"fitres": output_file(self.reporting_sub_dir, f"round_{ROUND}", TAG, f"{self.client_fitres_parameters_file_prefix}_{CID}.npz")}


class ConfigSaveClientsFitResStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveClientsFitRes"
    PYBISCUS_GROUP: ClassVar[str] = "Saving"
    name: Literal["saveclientsfitres"]

    config: ConfigSaveClientsFitResStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveClientsFitResStrategyDecorator(StrategyDecorator):
    """Saves the weights each client sends back at every round, in a round_<n> directory of the reports."""
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        self.base_strategy = base_strategy
        self.conf = conf

    # -------------------------------------------------------------------------

    def aggregate_fit(self, server_round, results, failures):

        aggregated, _ = super().aggregate_fit(server_round, results, failures)

        for client_proxy, fit_res in results:

            client_id = client_proxy.cid
            logm.console.log(f"Source is flower => client_id = {client_id}")
            logm.console.log(f"Source is metrics => cid = {fit_res.metrics['cid']}")

            result = fl.common.parameters_to_ndarrays(fit_res.parameters)

            np.savez(self.conf.output_path("fitres", round=server_round, cid=client_id), *result)

        return aggregated, {}
