from typing import ClassVar, List, Literal, Tuple
import flwr as fl
from flwr.common import Parameters

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

import numpy as np
from pydantic import BaseModel, ConfigDict

from pybiscus.core.ensure_filesystem import ensure_file_dir_exists, ensure_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# -------------------------------------------------------------------------

class ConfigSaveServerFitParamsDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = "rounds"
    server_aggregated_fit_parameters_file_name: str = "server_aggregated_fit_parameters.npz"

    model_config = ConfigDict(extra="forbid")


class ConfigSaveServerFitParamsDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveServerFitParams"
    name: Literal["saveserverfitparams"]

    config: ConfigSaveServerFitParamsDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveServerFitParamsStrategyDecorator(StrategyDecorator):
    """
    Decorator that save the base strategy server fit params
    """
    
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

        import pybiscus.core.pybiscuscontext as pcpc
        reporting_path = pcpc.pybiscus_context["reporting_path"]

        round_path = reporting_path / self.conf.reporting_sub_dir
        ensure_dir_exists(round_path)
        params_path = round_path / f"round_{server_round}" / self.conf.server_aggregated_fit_parameters_file_name
        ensure_file_dir_exists(params_path)
        np.savez(params_path, *global_weights)

        return base_config
    