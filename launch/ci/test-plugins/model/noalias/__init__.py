from typing import Literal

from pydantic import BaseModel, ConfigDict

from noop.lit_noop import ConfigNoop, LitNoop


# no PYBISCUS_ALIAS on purpose: the forms label it by its name, as the session form does
class ConfigModel_NoAlias(BaseModel):

    name: Literal["noalias"]
    config: ConfigNoop
    model_config = ConfigDict(extra="forbid")


def get_modules_and_configs():
    return {"noalias": LitNoop}, [ConfigModel_NoAlias]
