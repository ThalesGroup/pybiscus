
from typing import List, Tuple, Type
from pydantic import BaseModel

from basicstrategydecorator.metricdiffcomputestrategydecorator import ConfigMetricDiffComputeStrategyDecorator, MetricDiffComputeStrategyDecorator
from basicstrategydecorator.timediffcomputestrategydecorator import ConfigTimeDiffComputeStrategyDecorator, TimeDiffComputeStrategyDecorator

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (MetricDiffComputeStrategyDecorator, ConfigMetricDiffComputeStrategyDecorator),
        (TimeDiffComputeStrategyDecorator, ConfigTimeDiffComputeStrategyDecorator),
    ]
