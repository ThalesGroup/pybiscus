from typing import ClassVar, Literal
import flwr as fl

from flwr.server.strategy import Strategy

import numpy as np
from pydantic import BaseModel, ConfigDict

from pybiscus.core.ensure_filesystem import ensure_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigSaveClientsFitResStrategyDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = "rounds"
    client_fitres_parameters_file_prefix: str = "client_fitres_parameters"

    model_config = ConfigDict(extra="forbid")


class ConfigSaveClientsFitResStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "SaveClientsFitRes"
    name: Literal["saveclientsfitres"]

    config: ConfigSaveClientsFitResStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class SaveClientsFitResStrategyDecorator(StrategyDecorator):
    """
    Decorator that save clients results into files.
    """
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        self.base_strategy = base_strategy
        self.conf = conf

        import pybiscus.core.pybiscuscontext as pcpc
        self.reporting_path = pcpc.pybiscus_context["reporting_path"]

    # -------------------------------------------------------------------------

    def aggregate_fit(self, server_round, results, failures):

        aggregated, _ = super().aggregate_fit(server_round, results, failures)

        round_path = self.reporting_path / self.conf.reporting_sub_dir
        ensure_dir_exists(round_path)

        for client_proxy, fit_res in results:

            client_id = client_proxy.cid
            logm.console.log(f"Source is flower => client_id = {client_id}")
            logm.console.log(f"Source is metrics => cid = {fit_res.metrics['cid']}")

            result_path = round_path / f"round_{server_round}" / f"{self.conf.client_fitres_parameters_file_prefix}_{client_id}.npz"

            result = fl.common.parameters_to_ndarrays(fit_res.parameters)

            np.savez(result_path, *result)

        return aggregated, {}
