from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.flower.stoppingcriterion.basic.criteria import (ConfigMaxDuration, ConfigMetricPatience, ConfigMetricThreshold,
                                                              MaxDuration, MetricPatience, MetricThreshold)
from pybiscus.interfaces.flower.stoppingcriterion import StoppingCriterion

def get_modules_and_configs() -> Tuple[Dict[str, StoppingCriterion], List[BaseModel]]:

    registry = {
                    "threshold": MetricThreshold,
                    "patience":  MetricPatience,
                    "maxduration": MaxDuration,
                }
    configs  = [
                    ConfigMetricThreshold,
                    ConfigMetricPatience,
                    ConfigMaxDuration,
                ]

    return registry, configs
