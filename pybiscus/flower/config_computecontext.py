from enum import Enum
from typing import ClassVar, Union
from pydantic import BaseModel, ConfigDict

from pybiscus.core.registries import MetricsLoggerConfig
from pybiscus.flower.config_harware import ConfigHardware

class ConfigServerComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_compute_context"

    hardware: ConfigHardware
    metrics_logger: MetricsLoggerConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")


class ConfigClientComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "client_compute_context"

    hardware: ConfigHardware

    model_config = ConfigDict(extra="forbid")

