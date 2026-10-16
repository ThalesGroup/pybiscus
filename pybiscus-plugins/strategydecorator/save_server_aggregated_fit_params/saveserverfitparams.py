from typing import ClassVar, List, Literal, Tuple
import flwr as fl
from flwr.common import Parameters

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.core.reportingoutputs import ROUND, TAG, TaggedReportingOutputs, output_file
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# -------------------------------------------------------------------------

class ConfigSaveServerFitParamsDecoratorData(TaggedReportingOutputs):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = Field(default="rounds", description='subdirectory of the reporting directory, one round_<n> directory per round inside')
    server_aggregated_fit_parameters_file_name: str = Field(default="server_aggregated_fit_parameters.npz", description='file of the aggregated weights of the round')

    model_config = ConfigDict(extra="forbid")

    def reporting_outputs(self):
        return {"aggregated": output_file(self.reporting_sub_dir, f"round_{ROUND}", TAG, self.server_aggregated_fit_parameters_file_name)}


class ConfigSaveServerFitParamsDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveServerFitParams"
    PYBISCUS_GROUP: ClassVar[str] = "Saving"
    name: Literal["saveserverfitparams"]

    config: ConfigSaveServerFitParamsDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveServerFitParamsStrategyDecorator(StrategyDecorator):
    """Saves the aggregated weights of every round, in a round_<n> directory of the reports."""
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        """
        Args:
            base_strategy: the base strategy to decorate
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

        # get base config
        base_config = self.base_strategy.configure_fit( server_round, parameters, client_manager )
        
        global_weights = fl.common.parameters_to_ndarrays(parameters)

        np.savez(self.conf.output_path("aggregated", round=server_round), *global_weights)

        return base_config
    