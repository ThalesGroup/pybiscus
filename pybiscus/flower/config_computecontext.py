from enum import Enum
from typing import ClassVar, Union
from pydantic import BaseModel, ConfigDict

from pybiscus.core.registries import MetricsLoggerConfig

class ConfigHardware(BaseModel):
    """A Pydantic Model to validate the hardware configuration given by the user.

    This is a (partial) reproduction of the Fabric API found here:
    https://lightning.ai/docs/fabric/stable/api/generated/lightning.fabric.fabric.Fabric.html#lightning.fabric.fabric.Fabric

    Attributes
    ----------
    accelerator:
        the type of accelerator to use: gpu, cpu, auto... See the Fabric documentation for more details.
    devices: optional
        either an integer (the number of devices needed); a list of integers (the id of the devices); or
        the string "auto" to let Fabric choose the best option available.
    """

    PYBISCUS_CONFIG: ClassVar[str] = "hardware"

    class Accelerator(str, Enum):
        cpu  = "cpu"
        gpu  = "gpu"
        auto = "auto"

    accelerator: Accelerator = "auto"

    devices: Union[int, list[int], str] = "auto"

    model_config = ConfigDict(extra="forbid")


class ConfigServerComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "server_compute_context"

    hardware: ConfigHardware
    metrics_logger: MetricsLoggerConfig() # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")


class ConfigClientComputeContext(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "client_compute_context"

    hardware: ConfigHardware

    model_config = ConfigDict(extra="forbid")

