from typing import ClassVar, Literal

import flwr as fl
from pydantic import BaseModel, ConfigDict

from pybiscus.flower.strategy.fedavg.fedavgstrategy import ConfigFedAvgData, FedAvgFactory


class ConfigLintprobeNosuper(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Lint probe: aggregate_fit without super"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"

    name: Literal["lintprobe_nosuper"]
    config: ConfigFedAvgData

    model_config = ConfigDict(extra="forbid")


class LintprobeNosuper(fl.server.strategy.FedAvg):

    def aggregate_fit(self, server_round, results, failures):  # expect: strategy
        return None, {}


class LintprobeNosuperFactory(FedAvgFactory):
    flower_strategy_class = LintprobeNosuper


def get_modules_and_configs():
    return [(LintprobeNosuperFactory, ConfigLintprobeNosuper)]
