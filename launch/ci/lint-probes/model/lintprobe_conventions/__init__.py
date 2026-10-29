from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_conventions.lit_lintprobe_conventions import ConfigModel_LintprobeConventions, LitLintprobeConventions


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeConventions, ConfigModel_LintprobeConventions)]
