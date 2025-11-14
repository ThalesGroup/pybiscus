
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from save_all_clients_fit_in_params.saveclientsfitinparams import ConfigSaveAllClientsFitInParamsDecorator, SaveClientsFitInParamsStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "saveallclientsfitin" : SaveClientsFitInParamsStrategyDecorator,
        }
    configs  = [ConfigSaveAllClientsFitInParamsDecorator, ]

    return registry, configs

