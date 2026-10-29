from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_ok.lit_lintprobe_ok import ConfigModel_LintprobeOk, LitLintprobeOk


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeOk, ConfigModel_LintprobeOk)]
