
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from personalize_clients_fit_in_params.personalizeclientsfitinparams import PersonalizeClientsFitInParamsStrategyDecorator, ConfigPersonalizeClientsFitInParamsStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (PersonalizeClientsFitInParamsStrategyDecorator, ConfigPersonalizeClientsFitInParamsStrategyDecorator),
    ]
