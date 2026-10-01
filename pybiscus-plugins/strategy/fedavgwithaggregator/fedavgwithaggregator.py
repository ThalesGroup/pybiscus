from typing import ClassVar, Literal, Union

import flwr as fl
from flwr.common import FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.flower.strategy.fedavg.fedavgstrategy import ConfigFedAvgData, FedAvgFactory
from pybiscus.flower.flowerfitresultsaggregator.flowerfitresultsaggregatorusingweightedaverage.flowerfitresultsaggregatorusingweightedaverage import (
    ConfigFlowerFitResultsAggregatorUsingWeightedAverage,
    ConfigFlowerFitResultsAggregatorUsingWeightedAverageData,
)
from pybiscus.plugin.registries.flowerfitresultagregator_registry import FlowerFitResultsAggregatorConfig, flowerfitresultsaggregator_registry


class ConfigFedAvgWithAggregatorData(ConfigFedAvgData):
    """FedAvg whose new weights are computed by a flowerfitresultsaggregator plugin"""

    aggregator: FlowerFitResultsAggregatorConfig() = Field(  # pyright: ignore[reportInvalidTypeForm]
        default=ConfigFlowerFitResultsAggregatorUsingWeightedAverage(
            name="weightedaverage", config=ConfigFlowerFitResultsAggregatorUsingWeightedAverageData()),
        description="how the clients' weights are combined: weighted by their number of examples (FedAvg's), or a plain average...")


class ConfigFedAvgWithAggregator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvg with aggregator"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"

    name:   Literal["fedavgwithaggregator"]
    config: ConfigFedAvgWithAggregatorData

    model_config = ConfigDict(extra="forbid")


class FedAvgWithAggregator(fl.server.strategy.FedAvg):

    def __init__(self, *, aggregator, **kwargs):
        super().__init__(**kwargs)
        self.aggregator = aggregator

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        # Flower's checks (no results, refused failures) and metrics kept: only the weights change,
        # at the cost of a weighted average computed and then dropped
        parameters, metrics = super().aggregate_fit(server_round, results, failures)
        if parameters is None:
            return parameters, metrics
        return self.aggregator.aggregate(server_round, results, failures), metrics


class FedAvgWithAggregatorFactory(FedAvgFactory):
    flower_strategy_class = FedAvgWithAggregator

    def strategy_kwargs(self) -> dict:
        kwargs = super().strategy_kwargs()
        aggregator = kwargs.pop("aggregator")
        kwargs["aggregator"] = flowerfitresultsaggregator_registry()[aggregator["name"]](**aggregator["config"])
        return kwargs
