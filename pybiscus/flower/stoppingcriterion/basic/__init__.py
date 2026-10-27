from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.flower.stoppingcriterion.basic.criteria import (ConfigMaxDuration, ConfigMetricPatience, ConfigMetricThreshold,
                                                              MaxDuration, MetricPatience, MetricThreshold)
from pybiscus.interfaces.flower.stoppingcriterion import StoppingCriterion

def get_modules_and_configs() -> List[Tuple[Type[StoppingCriterion], Type[BaseModel]]]:

    return [
        (MetricThreshold, ConfigMetricThreshold),
        (MetricPatience, ConfigMetricPatience),
        (MaxDuration, ConfigMaxDuration),
    ]
