from typing import ClassVar, List, Literal, Tuple
import flwr as fl
from flwr.common import Parameters
from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.common import parameters_to_ndarrays

import numpy as np
from pydantic import BaseModel, ConfigDict

from pybiscus.core.ensure_filesystem import ensure_file_dir_exists, ensure_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigSaveAllClientsFitInParamsDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = "rounds"
    client_fitin_parameters_file_prefix: str = "client_fitin_parameters"

    model_config = ConfigDict(extra="forbid")


class ConfigSaveAllClientsFitInParamsDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveAllClientsFitInParams"
    name: Literal["saveallclientsfitin"]

    config: ConfigSaveAllClientsFitInParamsDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveClientsFitInParamsStrategyDecorator(StrategyDecorator):
    """
    Decorator that save all the base strategy clients fit in params
    useful when each client is given a dedicated value
    otherwise the servet fit params fit
    """
    
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

        import pybiscus.core.pybiscuscontext as pcpc
        reporting_path = pcpc.pybiscus_context["reporting_path"]

        # get base config
        fit_ins_list = self.base_strategy.configure_fit( server_round, parameters, client_manager )
        
        for client_proxy, fit_ins in fit_ins_list:

            client_weights = parameters_to_ndarrays(fit_ins.parameters)

            cid = client_proxy.cid

            round_path = reporting_path / self.conf.reporting_sub_dir
            ensure_dir_exists(round_path)
            params_path = round_path / f"round_{server_round}" / f"{self.conf.client_fitin_parameters_file_prefix}_{cid}.npz"
            ensure_file_dir_exists(params_path)
            np.savez(params_path, *client_weights)

        return fit_ins_list
