from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from omniscientalie.omniscientaliedecorator import ConfigOmniscientAlieDecorator, OmniscientAlieStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:  # pybiscus-lint: ignore=manifest (a test plugin: launch/campaign/test-plugins-conf.yml lists it)

    return [
        (OmniscientAlieStrategyDecorator, ConfigOmniscientAlieDecorator),
    ]
