import os
from enum import Enum
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

import wandb

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


class WandbMode(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    online = "online"        # sent to the W&B server as the run goes
    offline = "offline"      # kept under the experiment directory, sent later with "wandb sync <dir>"
    disabled = "disabled"    # nothing logged


class ConfigWandbLoggerFactoryData(BaseModel):
    """Weights & Biases run of the server, which logs every metric (the clients' too).
    project: W&B project; entity: team or user (unset: the account's default); name, group, tags:
    of the run (name unset: drawn by W&B); mode: online, offline (no network needed) or disabled;
    api_key_env_var: environment variable holding the API key, read only when set and present,
    otherwise W&B uses WANDB_API_KEY or the machine's "wandb login"."""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    project: str = "pybiscus"
    entity: Optional[str] = None
    name: Optional[str] = None
    group: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    mode: WandbMode = WandbMode.online
    # never the key itself: the configuration is saved with the experiment and shown in the forms
    api_key_env_var: str = "WANDB_API_KEY"

    model_config = ConfigDict(extra="forbid")


class ConfigWandbLoggerFactory(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Weights & Biases"

    name:   Literal["wandb"]
    config: ConfigWandbLoggerFactoryData

    model_config = ConfigDict(extra="forbid")

    # to emulate a dict
    def __getitem__(self, attName):
        return getattr(self, attName, None)


class WandbMetricsLogger:
    """the interface the other metrics loggers offer: a W&B run has log(), not log_metrics()"""

    def __init__(self, run):
        self.run = run

    def log_metrics(self, metrics, step=None):
        # no finish() call: nothing finalizes the metrics loggers, W&B closes its run at exit
        self.run.log(dict(metrics), step=step)


class WandbLoggerFactory(MetricsLoggerFactory):

    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_metricslogger(self, reporting_path):
        conf = self.config

        settings = {}
        api_key = os.environ.get(conf.api_key_env_var)
        if api_key:
            # passed to this run only: wandb.login() would write it to the user's ~/.netrc
            settings["api_key"] = api_key
        elif conf.mode == WandbMode.online and conf.api_key_env_var != "WANDB_API_KEY":
            logm.console.log(f"⚠️ W&B: {conf.api_key_env_var} is not set, relying on the machine's \"wandb login\"")

        try:
            run = wandb.init(
                project=conf.project,
                entity=conf.entity,
                name=conf.name,
                group=conf.group,
                tags=conf.tags or None,
                mode=conf.mode.value,
                # with the experiment's other files rather than a ./wandb of the current directory
                dir=str(reporting_path),
                config=pcpc.pybiscus_context.get(pcpc.SERVER_CONFIG),
                settings=wandb.Settings(**settings),
            )
        except Exception as error:
            raise PybiscusValueException(
                f"W&B run could not start ({error}). Online mode needs an API key: set "
                f"{conf.api_key_env_var} or run \"wandb login\"; offline mode needs no network."
            ) from error

        logm.console.log(f"W&B run {run.name} ({conf.mode.value}) in {reporting_path}")
        return WandbMetricsLogger(run)
