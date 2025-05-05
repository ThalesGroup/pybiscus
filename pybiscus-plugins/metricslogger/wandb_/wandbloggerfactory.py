
from enum import Enum
import os
from typing import ClassVar, Literal, Union

from pydantic import BaseModel, ConfigDict

import wandb

from pybiscus.core.metricslogger.interface.metricsloggerfactory import MetricsLoggerFactory

class EnvVar(BaseModel):

    env_var_name: str = "WANDB_API_KEY"    

    model_config = ConfigDict(extra="forbid")

class String(BaseModel):

    value: str = "xxxxxxxxxx"    

    model_config = ConfigDict(extra="forbid")

class Undefined(BaseModel):

    model_config = ConfigDict(extra="forbid")
    
class WandbRole(Enum):
    Client = True
    Server = False

class ConfigWandbLoggerFactoryParams(BaseModel):
    """
        project_name: Name of the W&B project
        entity_name: Optional name of the W&B entity (team or username)
        run_name: Optional name for this specific run
        run_group: Optional group to organize related runs
        job_type: Optional job type (e.g. 'server', 'client')
        config: Optional dictionary of configuration parameters to log
        is_client: Boolean indicating if this is a client
        partition_id: Optional client partition ID (required if is_client=True)
    """

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    project_name: str = "DefaultProjectName"
    entity_name:  str = "DefaultEntityName"
    run_name:     str = "DefaultRunName"
    run_group:    str = "DefaultRunGroup"
    job_type:     str = "DefaultJobType"
    # config: Optional[Dict[str, Any]] = None,
    #     config={
    #    "round": config["round"],
    # )
    # config={
    #     "model_checkpoint": model_checkpoint,
    #     "num_rounds": num_rounds,
    #     "fraction_fit": fraction_fit,
    #     "num_labels": num_labels,
    # },

    is_client:    WandbRole = WandbRole.Server.value
    # partition_id: int  = 1

    model_config = ConfigDict(extra="forbid")

class ConfigWandbLoggerFactoryData(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = """🚨 <span style="color: white; background-color: red;">Untested Wandb configuration</span> 🚨"""


    api_key_definition: Union[EnvVar, String, Undefined]
    params:             ConfigWandbLoggerFactoryParams

    model_config = ConfigDict(extra="forbid")

class ConfigWandbLoggerFactory(BaseModel):

    name:   Literal["wandb"]

    PYBISCUS_ALIAS: ClassVar[str] = "WanDb"

    config: ConfigWandbLoggerFactoryData

    model_config = ConfigDict(extra="forbid")

    # to emulate a dict
    def __getitem__(self, attName):
        return getattr(self, attName, None)


class WandbLoggerFactory(MetricsLoggerFactory):

    def __init__(self, root_dir, conf ):

        self.root_dir = root_dir
        self.conf = conf

    def get_logger(self):

        if wandb.run is not None:
            return wandb.run

        if isinstance(self.conf.api_key_definition, EnvVar):
            print("C'est une EnvVar")
            WANDB_API_KEY = os.getenv(self.conf.api_key_definition.env_var_name)
            os.environ["WANDB_API_KEY"] = WANDB_API_KEY
            wandb.init( )
        elif isinstance(self.conf.api_key_definition, String):
            print("C'est une String")
            wandb.init(self.conf.api_key_definition.value )
        elif isinstance(self.conf.api_key_definition, Undefined):
            print("C'est un Undefined")
            wandb.init( )
        else:
            return []

        wandb_server_run = wandb.init(**self.conf.params.model_dump())

        if wandb_server_run is None:
            return []
        else:
            return[wandb_server_run]
        
