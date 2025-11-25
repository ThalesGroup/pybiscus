
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from personalize_clients_fit_in_params.personalizeclientsfitinparams import PersonalizeClientsFitInParamsStrategyDecorator, ConfigPersonalizeClientsFitInParamsStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "personalizeclientsfitin" : PersonalizeClientsFitInParamsStrategyDecorator,
        }
    configs  = [ConfigPersonalizeClientsFitInParamsStrategyDecorator, ]

    return registry, configs
