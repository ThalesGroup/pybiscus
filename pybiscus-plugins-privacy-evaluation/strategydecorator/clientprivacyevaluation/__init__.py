
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator


from clientprivacyevaluation.fedmiaprivacyevaluation import ConfigFedMIAPrivacyEvaluationStrategyDecorator, FedMIAPrivacyEvaluationStrategyDecorator
# from clientprivacyevaluation.testmetricdiffcomputestrategydecorator import ConfigTestMetricDiffComputeStrategyDecorator, TestMetricDiffComputeStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (FedMIAPrivacyEvaluationStrategyDecorator, ConfigFedMIAPrivacyEvaluationStrategyDecorator),
        # (TestMetricDiffComputeStrategyDecorator, ConfigTestMetricDiffComputeStrategyDecorator),
    ]
