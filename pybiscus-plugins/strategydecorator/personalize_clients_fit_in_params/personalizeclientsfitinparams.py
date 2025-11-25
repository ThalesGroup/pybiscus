from typing import ClassVar, List, Literal, Tuple
import flwr as fl
from flwr.common import Parameters

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
from pybiscus.plugin.registries.resultmodifier_registry import ResultModifierConfig, resultmodifier_registry
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigPersonalizeClientsFitInParamsStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    result_modifier: ResultModifierConfig() # pyright: ignore[reportInvalidTypeForm]

    protect_model_weights: bool = True
    debug: bool = False

    model_config = ConfigDict(extra="forbid")


class ConfigPersonalizeClientsFitInParamsStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "PersonalizeClientsFitInParams"
    name: Literal["personalizeclientsfitin"]

    config: ConfigPersonalizeClientsFitInParamsStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class PersonalizeClientsFitInParamsStrategyDecorator(StrategyDecorator):
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

        # allocate a result modifier usign its class name

        # step 1 : find class by name in corresponding registry
        resultmodifier_class = resultmodifier_registry()[conf.result_modifier.name]

        # step 2 : invoke ctor with configuration
        self.result_modifier = resultmodifier_class(**conf.result_modifier.config.model_dump())

    # -------------------------------------------------------------------------

    # def aggregate_fit(self, server_round, results, failures):

    #     if self.conf.debug:
    #         logm.console.log(f"[{server_round}] PRSD aggregate_fit")

    #     aggregated_parameters, metrics = self.base_strategy.aggregate_fit(server_round, results, failures)

    #     if aggregated_parameters is None:
    #         logm.console.log("⚠️ No aggregated parameters from base strategy")
    #     else:
    #         nds = fl.common.parameters_to_ndarrays(aggregated_parameters)
    #         if self.conf.debug:
    #             logm.console.log(f"✅ Aggregated {len(nds)} ndarrays")

    #     return aggregated_parameters, metrics or {}

    # -------------------------------------------------------------------------

    def configure_fit(
        self,
        server_round: int,
        parameters: Parameters,
        client_manager: ClientManager,
    ) -> List[Tuple[ClientProxy, fl.common.FitIns]]:
        """send personalized models to clients"""

        if self.conf.debug:
            logm.console.log(f"[{server_round}] PRSD configure_fit")

        # get base config
        base_config = self.base_strategy.configure_fit( server_round, parameters, client_manager )
        
        # replace parameters by a personalized version
        personalized_config = []

        global_weights = fl.common.parameters_to_ndarrays(parameters)
        # logm.console.log( f"PR::CF global weights=[{" ".join(" ".join(map(str, w)) for w in global_weights)}]" )

        if self.conf.protect_model_weights:
            # save model weights as they are modified into the result modifyer
            from pybiscus.core.pybiscuscontext import pybiscus_context
            from pybiscus.flower.utils_server import set_params, get_params
    
            model = pybiscus_context["model"]
            saved_weights = get_params(model)

        for client_proxy, fit_ins in base_config:

            cid = client_proxy.cid

            if self.conf.debug:
                logm.console.log(f"PR configure_fit( round={server_round}, cid={cid}")
                # logm.console.log( f"PR::CF global weights={" ".join(" ".join(map(str, w)) for w in global_weights)}" )

            # call the configurated result modifyer
            personalized_weights = self.result_modifier.modify( server_round, cid, global_weights )

            if self.conf.debug:
                logm.console.log( f"PR::CF client weights len ={len(personalized_weights)}" )
                # logm.console.log( f"PR::CF client weights=[{" ".join(" ".join(map(str, w)) for w in personalized_weights)}]" )

            custom_params = fl.common.ndarrays_to_parameters(personalized_weights)

            personalized_fit_ins = fl.common.FitIns( parameters=custom_params, config=fit_ins.config )

            personalized_config.append((client_proxy, personalized_fit_ins))

            if self.conf.protect_model_weights:
                # restore model weights as they were modified into the result modifyer
                set_params(model, saved_weights)

        return personalized_config
