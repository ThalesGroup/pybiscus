from typing import ClassVar, Literal

from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict

import pybiscus.core.pybiscus_logger as logm
from pybiscus.flower.sessionlink import ConfigSessionLink, DirectoryLink, scalar_metrics
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# The server of a lower level follows its upper level round for round: each round trains the upper
# level's model of that round, and its aggregate goes up through the relay. Both sessions have the
# same model and number of rounds (imposed by the managers).


class ConfigUpperLevelLinkDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Upper level link"
    PYBISCUS_GROUP: ClassVar[str] = "Hierarchy"
    # the outermost: the other decorators see the upper level's model, and what goes up is the
    # aggregate after clipping or DP
    PYBISCUS_LAST: ClassVar[bool] = True

    name:   Literal["upperlevellink"]
    config: ConfigSessionLink

    model_config = ConfigDict(extra="forbid")


class UpperLevelLinkDecorator(StrategyDecorator):

    def __init__(self, base_strategy, config: ConfigSessionLink):
        super().__init__(base_strategy)
        self.link = DirectoryLink(config)
        self.first_model = None

    def initialize_parameters(self, client_manager):
        self.base_strategy.initialize_parameters(client_manager)
        # the upper level's model of round 1, its initial one: the evaluation of round 0 measures
        # the model both levels start from, not one this level never trains
        self.first_model = ndarrays_to_parameters(self.link.wait_model(1))
        return self.first_model

    def configure_fit(self, server_round, parameters, client_manager):
        if server_round == 1 and self.first_model is not None:
            upper_model = self.first_model
        else:
            upper_model = ndarrays_to_parameters(self.link.wait_model(server_round))
        self.first_model = None
        return self.base_strategy.configure_fit(server_round, upper_model, client_manager)

    def aggregate_fit(self, server_round, results, failures):
        parameters, metrics = self.base_strategy.aggregate_fit(server_round, results, failures)
        if parameters is None:
            # said at once: the relay would wait for its whole timeout otherwise
            self.link.publish_failure(server_round, f"no aggregate ({len(results)} results, {len(failures)} failures)")
            return parameters, metrics
        num_examples = sum(fit_res.num_examples for _, fit_res in results)
        self.link.publish_aggregate(server_round, parameters_to_ndarrays(parameters), num_examples, scalar_metrics(metrics))
        logm.console.log(f"🔗 round {server_round}: aggregate of {num_examples} examples sent to the upper level")
        return parameters, metrics
