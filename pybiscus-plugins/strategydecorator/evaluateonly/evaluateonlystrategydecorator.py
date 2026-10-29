from typing import ClassVar, List, Literal, Tuple

from flwr.common import FitIns, Parameters
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator


class ConfigEvaluateOnlyStrategyDecoratorData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    empty_configuration: bool = True

    model_config = ConfigDict(extra="forbid")


class ConfigEvaluateOnlyStrategyDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "EvaluateOnly"
    PYBISCUS_GROUP: ClassVar[str] = "Evaluation"
    name: Literal["evaluateonly"]

    config: ConfigEvaluateOnlyStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


class EvaluateOnlyStrategyDecorator(StrategyDecorator):
    """No client trains: each round only evaluates the server's model, on the server's test data and on
    each client's validation data (federated evaluation, with the onnxmodel model for instance).
    Not with server_run.schedule nor stop_without_new_data: a round in which no client trained is not counted there."""

    def __init__(self, base_strategy, config: ConfigEvaluateOnlyStrategyDecoratorData):
        super().__init__(base_strategy)

    def configure_fit(self, server_round: int, parameters: Parameters, client_manager: ClientManager
                      ) -> List[Tuple[ClientProxy, FitIns]]:
        logm.console.log(f"[{server_round}] evaluateonly: no client trains in this round")
        # the server's fit_round ends on an empty list without aggregating: the parameters stay those of the start
        return []
