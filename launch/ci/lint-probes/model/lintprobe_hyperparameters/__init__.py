from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_hyperparameters.lit_lintprobe_hyperparameters import ConfigModel_LintprobeHyperparameters, LitLintprobeHyperparameters


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeHyperparameters, ConfigModel_LintprobeHyperparameters)]
