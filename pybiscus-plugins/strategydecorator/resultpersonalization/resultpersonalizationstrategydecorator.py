from pathlib import Path
from typing import ClassVar, List, Literal, Tuple, Optional, Dict
import flwr as fl
from flwr.common import (
    Parameters, 
    FitRes, 
    Scalar,
    ndarrays_to_parameters as flw_ndarrays_to_parameters,
    parameters_to_ndarrays as flw_parameters_to_ndarrays,
)

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

import numpy as np
from pydantic import BaseModel, ConfigDict

from pybiscus.core.ensure_filesystem import ensure_file_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
from pybiscus.plugin.registries.resultmodifier_registry import ResultModifierConfig, resultmodifier_registry
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigPersonalizationStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    result_modifier: ResultModifierConfig() # pyright: ignore[reportInvalidTypeForm]

    protect_model_weights: bool = True
    save_as_np: bool = False

    model_config = ConfigDict(extra="forbid")


class ConfigPersonalizationStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "ResultPersonalization"
    name: Literal["resultpersonalization"]

    config: ConfigPersonalizationStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class PersonalizedResultStrategyDecorator(StrategyDecorator):
    """
    Decorator that add result personalization to a Flower strategy.
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

        self.personalized_models: Dict[str, Parameters] = {}

        # allocate a result modifier usign its class name

        # step 1 : find class by name in corresponding registry
        resultmodifier_class = resultmodifier_registry()[conf.result_modifier.name]

        # step 2 : invoke ctor with configuration
        self.result_modifier = resultmodifier_class(**conf.result_modifier.config.model_dump())

    # -------------------------------------------------------------------------

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[BaseException],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """perform aggregate then compute personalized version on a per client basis
        
        class FitRes:
            status: Status           # training status
            parameters: Parameters   # updated model parameters
            num_examples: int        # training samples nb
            metrics: Dict[str, Scalar]

        class Parameters:
            tensors: List[bytes]    # tensors list byte-serialized
            tensor_type: str        # ex: "numpy.ndarray"

        Scalar = Union[bool, bytes, float, int, str]

        """
        
        # call base strategy aggregation
        aggregated_params, metrics = self.base_strategy.aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_params is None:
            return None, metrics

        import pybiscus.core.pybiscuscontext as pcpc
        reporting_path = pcpc.pybiscus_context["reporting_path"]
        
        # global_weights is a NDArrays
        global_weights = flw_parameters_to_ndarrays(aggregated_params)

        # Save aggregated weights as np (optional)
        if self.conf.save_as_np:      
            checkpoint_aggregated_path = reporting_path / f"personnalized_checkpoints/round_{server_round}/aggregated.npz"
            ensure_file_dir_exists(checkpoint_aggregated_path)
            np.savez(checkpoint_aggregated_path, *global_weights)

        self.personalized_models.clear()

        if self.conf.protect_model_weights:
            from pybiscus.core.pybiscuscontext import pybiscus_context
            from pybiscus.flower.utils_server import set_params, get_params

            model = pybiscus_context["model"]
            saved_weights = get_params(model)

        for client_proxy, _ in results:
            cid = client_proxy.cid
            
            # personalized client weights
            personalized_weights = self.result_modifier.modify( server_round, cid, global_weights )

            # Save personalized weights as np (optional)
            if self.conf.save_as_np:      
                checkpoint_client_path = reporting_path / f"personnalized_checkpoints/round_{server_round}/client_{cid}.npz"
                ensure_file_dir_exists(checkpoint_aggregated_path)
                np.savez(checkpoint_client_path, *personalized_weights)

            self.personalized_models[cid] = flw_ndarrays_to_parameters( personalized_weights )

        if self.conf.protect_model_weights:
            set_params(model, saved_weights)

        return aggregated_params, metrics

    # -------------------------------------------------------------------------

    def configure_fit(
        self,
        server_round: int,
        parameters: Parameters,
        client_manager: ClientManager,
    ) -> List[Tuple[ClientProxy, fl.common.FitIns]]:
        """send personalized models to clients"""
        
        # get base config
        base_config = self.base_strategy.configure_fit(
            server_round, parameters, client_manager
        )
        
        # replace parameters by a personalized version
        personalized_config = []

        for client_proxy, fit_ins in base_config:
            cid = client_proxy.cid
            
            # used personalized model or global in unavailable
            #TODO if round > 0 and cid not in self.personalized_models:
            if cid not in self.personalized_models:
                logm.console.log(f"❌ No personalized Result for client {cid}")

            custom_params = self.personalized_models.get(cid, parameters)
            
            personalized_fit_ins = fl.common.FitIns(
                parameters=custom_params,
                config=fit_ins.config
            )
            personalized_config.append((client_proxy, personalized_fit_ins))
        
        return personalized_config
