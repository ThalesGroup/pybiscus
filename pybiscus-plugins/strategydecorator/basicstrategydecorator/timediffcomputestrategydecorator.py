from typing import ClassVar, List, Literal, Tuple, Optional, Dict, Union
from typing import List, Tuple, Optional, Dict, Union
from flwr.common import EvaluateRes, Scalar
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm
import time

# -----------------------------------------------

class ConfigTimeDiffComputeStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    empty_configuration: bool = True

    model_config = ConfigDict(extra="forbid")


class ConfigTimeDiffComputeStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "TimeDiffCompute"
    name: Literal["timediffcompute"]

    config: ConfigTimeDiffComputeStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


class TimeDiffComputeStrategyDecorator(StrategyDecorator):

    def __init__(self, base_strategy, config: ConfigTimeDiffComputeStrategyDecorator):
        super().__init__(base_strategy)

        self.previous_time: Optional[float] = None
        
    def aggregate_evaluate( self, 
                        server_round: int,
                        results: List[Tuple[ClientProxy, EvaluateRes]], 
                        failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]],
                    ) -> Tuple[Optional[float], Dict[str, Scalar]]:

        # delegate to base_strategy the computation
        metric, metrics_dict = self.base_strategy.aggregate_evaluate(server_round, results, failures)

        current_time = time.time()

        if self.previous_time is None:
            logm.console.log(f"⏱️⚖️⏱️ = 🧐🔢 previous time is None 🈚🕳️")
        else:
        
            logm.console.log(f"⏱️⚖️⏱️ = 🧐🔢 time diff is {current_time - self.previous_time:.2f}s")

        self.previous_time = current_time

        return metric, metrics_dict
