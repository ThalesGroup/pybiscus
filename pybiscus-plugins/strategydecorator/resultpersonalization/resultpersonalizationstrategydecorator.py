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

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm
from pybiscus.plugin.registries.resultmodifier_registry import ResultModifierConfig, resultmodifier_registry

# -------------------------------------------------------------------------

class ConfigPersonalizationStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    result_modifier: ResultModifierConfig() # pyright: ignore[reportInvalidTypeForm]

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
        self.personalized_models: Dict[str, Parameters] = {}

        print(conf)
        print(conf.result_modifier)

        resultmodifier_class = resultmodifier_registry()[conf.result_modifier.name]
        self.result_modifier = resultmodifier_class(**conf.result_modifier.config.model_dump())

    # -------------------------------------------------------------------------

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[BaseException],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """perform aggregate then compute personalized cversion on a per client basis"""
        
        # Step 1 : calling base strategy aggregation
        aggregated_params, metrics = self.base_strategy.aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_params is None:
            return None, metrics
        
        # Step 2 : personalization per client
        global_weights = flw_parameters_to_ndarrays(aggregated_params)
        
        self.personalized_models.clear()

        for client_proxy, _ in results:
            cid = client_proxy.cid
            
            # Apply the personalization
            personalized_weights = self.result_modifier.modify( server_round, cid, global_weights )
            
            self.personalized_models[cid] = flw_ndarrays_to_parameters( personalized_weights )
        
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
            custom_params = self.personalized_models.get(cid, parameters)
            
            personalized_fit_ins = fl.common.FitIns(
                parameters=custom_params,
                config=fit_ins.config
            )
            personalized_config.append((client_proxy, personalized_fit_ins))
        
        return personalized_config
