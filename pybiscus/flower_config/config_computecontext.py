from typing import ClassVar
from pydantic import BaseModel, ConfigDict

from pybiscus.plugin.registries import MetricsLoggerConfig
from pybiscus.flower_config.config_hardware import ConfigHardware

class ConfigServerComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_compute_context"

    hardware: ConfigHardware
    metrics_loggers: list[MetricsLoggerConfig()] # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")


class ConfigClientComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "client_compute_context"

    hardware: ConfigHardware

    model_config = ConfigDict(extra="forbid")

