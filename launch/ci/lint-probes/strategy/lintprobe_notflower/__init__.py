from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory


class ConfigLintprobeNotflower(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Lint probe: not a FlowerStrategyFactory"
    PYBISCUS_GROUP: ClassVar[str] = "Averaging"

    name: Literal["lintprobe_notflower"]

    model_config = ConfigDict(extra="forbid")


class LintprobeNotflowerFactory(FabricStrategyFactory):  # expect: strategy
    pass


def get_modules_and_configs():
    return [(LintprobeNotflowerFactory, ConfigLintprobeNotflower)]
