
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator


from clientprivacyevaluation.fedmiaprivacyevaluation import ConfigFedMIAPrivacyEvaluationStrategyDecorator, FedMIAPrivacyEvaluationStrategyDecorator
# from clientprivacyevaluation.testmetricdiffcomputestrategydecorator import ConfigTestMetricDiffComputeStrategyDecorator, TestMetricDiffComputeStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
                    "fedmiaprivacyevaluation": FedMIAPrivacyEvaluationStrategyDecorator,
                    # "testmetricdiffcompute": TestMetricDiffComputeStrategyDecorator,

                }
    configs  = [
                    ConfigFedMIAPrivacyEvaluationStrategyDecorator,
                    # ConfigTestMetricDiffComputeStrategyDecorator,
                ]

    return registry, configs
