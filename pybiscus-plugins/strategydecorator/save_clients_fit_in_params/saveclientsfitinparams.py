from typing import ClassVar, List, Literal, Tuple
import flwr as fl
from flwr.common import Parameters
from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.common import parameters_to_ndarrays

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.core.reportingoutputs import CID, ROUND, TAG, TaggedReportingOutputs, output_file
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigSaveClientsFitInParamsDecoratorData(TaggedReportingOutputs):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = Field(default="rounds", description='subdirectory of the reporting directory, one round_<n> directory per round inside')
    client_fitin_parameters_file_prefix: str = Field(default="client_fitin_parameters", description='prefix of the files of the weights sent to each client')

    model_config = ConfigDict(extra="forbid")

    def reporting_outputs(self):
        return {"fitin": output_file(self.reporting_sub_dir, f"round_{ROUND}", TAG, f"{self.client_fitin_parameters_file_prefix}_{CID}.npz")}


class ConfigSaveClientsFitInParamsDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveClientsFitInParams"
    PYBISCUS_GROUP: ClassVar[str] = "Saving"
    name: Literal["saveclientsfitin"]

    config: ConfigSaveClientsFitInParamsDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveClientsFitInParamsStrategyDecorator(StrategyDecorator):
    """Saves the weights sent to each client at every round, in a round_<n> directory of the reports:
    useful when each client gets its own version of the model (personalizeclientsfitin)."""
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        """
        Args:
            base_strategy: the base strategy to decorate
            result_modifier: configuration of the result modifier
        """
        self.base_strategy = base_strategy
        self.conf = conf

    # -------------------------------------------------------------------------

    def configure_fit(
        self,
        server_round: int,
        parameters: Parameters,
        client_manager: ClientManager,
    ) -> List[Tuple[ClientProxy, fl.common.FitIns]]:
        """send personalized models to clients"""

        # get base config
        fit_ins_list = self.base_strategy.configure_fit( server_round, parameters, client_manager )
        
        for client_proxy, fit_ins in fit_ins_list:

            client_weights = parameters_to_ndarrays(fit_ins.parameters)

            cid = client_proxy.cid

            np.savez(self.conf.output_path("fitin", round=server_round, cid=cid), *client_weights)

        return fit_ins_list
