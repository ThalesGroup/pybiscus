from typing import ClassVar, Literal

import flwr as fl
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.flower.flowerstrategy import ConfigFlowerFailuresData, FlowerStrategyFactory

# Flower's FedAvg used as it is, in the core so that Pybiscus has a strategy without any plugin.
# The aggregation stays Flower's: a rewritten one, inherited, turns any subclass into a FedAvg.


class ConfigFedAvgData(ConfigFlowerFailuresData):
    """Parameters of Flower's FedAvg, see flwr.server.strategy.FedAvg."""
    inplace: bool = Field(default=True, description='aggregate in place, saving memory; same result')


class ConfigFedAvg(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedAvg"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"

    name:   Literal["fedavg"]
    config: ConfigFedAvgData

    model_config = ConfigDict(extra="forbid")


class FedAvgFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvg
