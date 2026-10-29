from typing import List, Tuple, Type

from pydantic import BaseModel

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

from lintprobe_nogroup.lintprobe_nogroupdecorator import ConfigLintprobeNogroupDecorator, LintprobeNogroupStrategyDecorator


def get_modules_and_configs() -> List[Tuple[Type[StrategyDecorator], Type[BaseModel]]]:
    return [(LintprobeNogroupStrategyDecorator, ConfigLintprobeNogroupDecorator)]
