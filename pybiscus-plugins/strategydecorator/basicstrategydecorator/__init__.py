
from typing import Dict, List, Tuple
from pydantic import BaseModel

from basicstrategydecorator.metricdiffcomputestrategydecorator import ConfigMetricDiffComputeStrategyDecorator, MetricDiffComputeStrategyDecorator
from basicstrategydecorator.timediffcomputestrategydecorator import ConfigTimeDiffComputeStrategyDecorator, TimeDiffComputeStrategyDecorator

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "metricdiffcompute": MetricDiffComputeStrategyDecorator,
        "timediffcompute":   TimeDiffComputeStrategyDecorator,
        }
    configs  = [ConfigMetricDiffComputeStrategyDecorator, ConfigTimeDiffComputeStrategyDecorator,]

    return registry, configs
