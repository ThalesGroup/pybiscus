from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_nosignature.lit_lintprobe_nosignature import ConfigModel_LintprobeNosignature, LitLintprobeNosignature


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeNosignature, ConfigModel_LintprobeNosignature)]
