from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator


class ConfigLintprobeNogroupDecoratorData(BaseModel):
    """the settings of the lintprobe_nogroup decorator"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    every: int = Field(default=1, ge=1, description="rounds between two lines of the log")

    model_config = ConfigDict(extra="forbid")


class ConfigLintprobeNogroupDecorator(BaseModel):  # expect: group

    PYBISCUS_ALIAS: ClassVar[str] = "LintprobeNogroup"
    # the family it is listed under in the forms: Metrics, Saving, Privacy, Robustness...
    # rules checked by `server check` and in the form; see docs/plugins.md
    # PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = ("serverdpfixed",)
    # PYBISCUS_AFTER: ClassVar[tuple] = ("personalizeclientsfitin",)

    # the registry key: what an item of `server_strategy.pipeline` names
    name: Literal["lintprobe_nogroup"]
    config: ConfigLintprobeNogroupDecoratorData

    model_config = ConfigDict(extra="forbid")


class LintprobeNogroupStrategyDecorator(StrategyDecorator):
    """TODO: what the lintprobe_nogroup decorator does around the strategy, in one paragraph: the plugins
    reference shows it. As generated: logs how many clients answered each round."""

    def __init__(self, base_strategy, config: ConfigLintprobeNogroupDecoratorData):
        super().__init__(base_strategy)
        self.config = config

    def aggregate_fit(self, server_round, results, failures):
        if server_round % self.config.every == 0:
            examples = sum(fit_res.num_examples for _, fit_res in results)
            logm.console.log(f"lintprobe_nogroup: round {server_round}, {len(results)} result(s) on {examples} example(s), {len(failures)} failure(s)")
        # the decorated strategy aggregates: every other method is left to it by StrategyDecorator
        return super().aggregate_fit(server_round, results, failures)
