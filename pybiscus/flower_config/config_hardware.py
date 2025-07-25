from enum import Enum
from typing import ClassVar, Union
from pydantic import BaseModel, ConfigDict

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

        

        
    copy of the source code from installed package (provision for future enhancements):
            
    class Fabric:
        Fabric accelerates your PyTorch training or inference code with minimal changes required.

        - Automatic placement of models and data onto the device.
        - Automatic support for mixed and double precision (smaller memory footprint).
        - Seamless switching between hardware (CPU, GPU, TPU) and distributed training strategies
        (data-parallel training, sharded training, etc.).
        - Automated spawning of processes, no launch utilities required.
        - Multi-node support.

        Args:
            accelerator: The hardware to run on. Possible choices are:
                ``"cpu"``, ``"cuda"``, ``"mps"``, ``"gpu"``, ``"tpu"``, ``"auto"``.
            strategy: Strategy for how to run across multiple devices. Possible choices are:
                ``"dp"``, ``"ddp"``, ``"ddp_spawn"``, ``"deepspeed"``, ``"fsdp"``.
            devices: Number of devices to train on (``int``), which GPUs to train on (``list`` or ``str``), or ``"auto"``.
                The value applies per node.
            num_nodes: Number of GPU nodes for distributed training.
            precision: Double precision (``"64"``), full precision (``"32"``), half precision AMP (``"16-mixed"``),
                or bfloat16 precision AMP (``"bf16-mixed"``).
            plugins: One or several custom plugins
            callbacks: A single callback or a list of callbacks. A callback can contain any arbitrary methods that
                can be invoked through :meth:`~lightning.fabric.fabric.Fabric.call` by the user.
            loggers: A single logger or a list of loggers. See :meth:`~lightning.fabric.fabric.Fabric.log` for more
                information.

    
        def __init__(
            self,
            *,
            accelerator: Union[str, Accelerator] = "auto",
            strategy: Union[str, Strategy] = "auto",
            devices: Union[List[int], str, int] = "auto",
            num_nodes: int = 1,
            precision: Optional[_PRECISION_INPUT] = None,
            plugins: Optional[Union[_PLUGIN_INPUT, List[_PLUGIN_INPUT]]] = None,
            callbacks: Optional[Union[List[Any], Any]] = None,
            loggers: Optional[Union[Logger, List[Logger]]] = None,
        ) -> None:
"""

    PYBISCUS_CONFIG: ClassVar[str] = "hardware"

    class Accelerator(str, Enum):
        cpu  = "cpu"
        # cuda = "cuda"
        # mps  = "mps"
        gpu  = "gpu"
        # tpu  = "tpu"
        auto = "auto"

    accelerator: Accelerator = "auto"

    # TODO: check devices
    # devices: Union[int, list[int], str] = "auto"
    # NB: int means the requested number of devices
    devices: Union[int, str] = "auto"

    model_config = ConfigDict(extra="forbid")
