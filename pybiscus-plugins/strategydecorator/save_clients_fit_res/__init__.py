
from typing import Dict, List, Tuple
from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from save_clients_fit_res.saveclientsfitres import ConfigSaveClientsFitResStrategyDecorator, SaveClientsFitResStrategyDecorator

def get_modules_and_configs() -> Tuple[Dict[str, StrategyDecorator], List[BaseModel]]:

    registry = {
        "saveclientsfitres" : SaveClientsFitResStrategyDecorator,
        }
    configs  = [ConfigSaveClientsFitResStrategyDecorator, ]

    return registry, configs
