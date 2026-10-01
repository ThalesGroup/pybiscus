from typing import ClassVar, Optional
from pydantic import BaseModel, ConfigDict, Field

from pybiscus.plugin.registries.metriclogger_registry import MetricsLoggerConfig
from pybiscus.flower_config.config_hardware import ConfigHardware

class ConfigServerComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_compute_context"

    hardware: ConfigHardware= Field(description='accelerator and devices of the server')
    metrics_loggers: list[MetricsLoggerConfig()] = Field(description="where the server's metrics go (TensorBoard, the session manager's webhook, W&B...)")# pyright: ignore[reportInvalidTypeForm]
    # PyTorch's CPU threads (all the physical cores if unset); never set by the manager: the
    # server computes while its clients wait, it only competes with other sessions or jobs
    num_threads: Optional[int] = Field(default=None, ge=1, description="PyTorch's CPU threads; all the physical cores if unset")

    model_config = ConfigDict(extra="forbid")


class ConfigClientComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "client_compute_context"

    hardware: ConfigHardware= Field(description='accelerator and devices of the client')
    # PyTorch's CPU threads (all the physical cores if unset): clients sharing a machine each take
    # every core otherwise; in a session, the manager may share the cores between them
    num_threads: Optional[int] = Field(default=None, ge=1, description="PyTorch's CPU threads; all the physical cores if unset (in a session, the manager may share the cores between the clients of a machine)")

    model_config = ConfigDict(extra="forbid")

