from typing import List, Tuple, Type

import lightning.pytorch as pl
from pydantic import BaseModel

from lintprobe_signature.lit_lintprobe_signature import ConfigModel_LintprobeSignature, LitLintprobeSignature


def get_modules_and_configs() -> List[Tuple[Type[pl.LightningModule], Type[BaseModel]]]:
    return [(LitLintprobeSignature, ConfigModel_LintprobeSignature)]
