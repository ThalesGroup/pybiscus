from typing import ClassVar, List, Literal, Tuple, Optional, Dict, Union
from typing import List, Tuple, Optional, Dict, Union
from flwr.common import EvaluateRes, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -----------------------------------------------

class ConfigMetricDiffComputeStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    empty_configuration: bool = True

    model_config = ConfigDict(extra="forbid")


class ConfigMetricDiffComputeStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "MetricDiffCompute"
    name: Literal["metricdiffcompute"]

    config: ConfigMetricDiffComputeStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


class MetricDiffComputeStrategyDecorator(StrategyDecorator):

    def __init__(self, base_strategy, config: ConfigMetricDiffComputeStrategyDecorator):
        super().__init__(base_strategy)

        self.previous_metric: Optional[float] = None
        
    def aggregate_evaluate( self, 
                        server_round: int,
                        results: List[Tuple[ClientProxy, EvaluateRes]], 
                        failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]],
                    ) -> Tuple[Optional[float], Dict[str, Scalar]]:

        # delegate to base_strategy the computation
        metric, metrics_dict = self.base_strategy.aggregate_evaluate(server_round, results, failures)

        if metric is None:
            logm.console.log(f"📊⚖️📊 = 🧐🔢 metric is None 🈚🕳️")
            return None, metrics_dict
        
        if self.previous_metric is not None:
            logm.console.log(f"📊⚖️📊 = 🧐🔢 metric diff is {abs(self.previous_metric - metric):.4f}")

        self.previous_metric = metric

        return self.previous_metric, metrics_dict
