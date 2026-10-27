
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from save_clients_fit_in_params.saveclientsfitinparams import ConfigSaveClientsFitInParamsDecorator, SaveClientsFitInParamsStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (SaveClientsFitInParamsStrategyDecorator, ConfigSaveClientsFitInParamsDecorator),
    ]

