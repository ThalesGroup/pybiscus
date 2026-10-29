from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_interface.lit_lintprobe_interface import ConfigModel_LintprobeInterface, LitLintprobeInterface


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeInterface, ConfigModel_LintprobeInterface)]
