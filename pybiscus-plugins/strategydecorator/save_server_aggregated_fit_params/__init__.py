
from typing import List, Tuple, Type
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from save_server_aggregated_fit_params.saveserverfitparams import ConfigSaveServerFitParamsDecorator, SaveServerFitParamsStrategyDecorator

def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:

    return [
        (SaveServerFitParamsStrategyDecorator, ConfigSaveServerFitParamsDecorator),
    ]

