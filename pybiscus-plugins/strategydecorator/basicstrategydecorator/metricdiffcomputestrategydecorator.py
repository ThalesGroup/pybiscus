from typing import ClassVar, List, Literal, Tuple, Optional, Dict, Union
from typing import List, Tuple, Optional, Dict, Union
from flwr.common import EvaluateRes, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.gui_events as gui_events

# -----------------------------------------------

class ConfigMetricDiffComputeStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    empty_configuration: bool = True

    model_config = ConfigDict(extra="forbid")


class ConfigMetricDiffComputeStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "MetricDiffCompute"
    PYBISCUS_GROUP: ClassVar[str] = "Metrics"
    name: Literal["metricdiffcompute"]

    config: ConfigMetricDiffComputeStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


class MetricDiffComputeStrategyDecorator(StrategyDecorator):
    """After each federated evaluation, the change of the main metric since the previous round, sent to
    the session manager's page (its loss · metric diff panel)."""

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
            gui_events.log_no_evaluation_metric(server_round)
            return None, metrics_dict
        
        if self.previous_metric is not None:
            gui_events.log_metric_diff(abs(self.previous_metric - metric), server_round)

        self.previous_metric = metric

        return self.previous_metric, metrics_dict
