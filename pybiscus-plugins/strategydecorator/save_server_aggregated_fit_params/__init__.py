
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from save_server_aggregated_fit_params.saveserverfitparams import ConfigSaveServerFitParamsDecorator, SaveServerFitParamsStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "saveserverfitparams" : SaveServerFitParamsStrategyDecorator,
        }
    configs  = [ConfigSaveServerFitParamsDecorator, ]

    return registry, configs

