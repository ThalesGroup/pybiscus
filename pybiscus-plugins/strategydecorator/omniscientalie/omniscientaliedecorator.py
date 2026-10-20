from typing import ClassVar, Literal, Optional

import numpy as np
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# The worst case of "A Little Is Enough" (Baruch et al., 2019), to measure the defenses against it:
# the attackers know the honest updates of the round. Only the server sees them all, so the attack
# is simulated here: the updates of the clients flagged byzantine (byzantine client plugin, attack
# none) are replaced by mean - z * std of the honest ones. The colluders of the client-side attack
# only estimate them from their own updates, which made it almost honest (DEVLOG, ALIE campaign).
# Declared in launch/campaign/test-plugins-conf.yml only: never in a real session's forms.


class ConfigOmniscientAlieDecoratorData(BaseModel):
    """replaces the updates of the clients whose fit metrics carry byzantine by mean - z * std of the
    honest updates, coordinate by coordinate; z: unset, the paper's value for the round's numbers of
    clients and attackers"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    z: Optional[float] = Field(title="Deviation (z)", default=None, gt=0, description="deviation sent, in honest standard deviations; unset: computed from the round's numbers of clients and attackers (0.57 for 2 of 7)")
    from_round: int = Field(default=1, ge=1, description="first round attacked")

    model_config = ConfigDict(extra="forbid")


class ConfigOmniscientAlieDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Omniscient ALIE (robustness tests)"
    PYBISCUS_GROUP: ClassVar[str] = "Robustness"
    # the defenses must see the forged updates: this decorator wraps them
    PYBISCUS_AFTER: ClassVar[tuple] = ("clipping", "fltrust", "foolsgold", "serverdpfixed", "serverdpadaptive")
    # the updates are measured against the global model, not what each client was sent
    PYBISCUS_INCOMPATIBLE_WITH: ClassVar[tuple] = ("personalizeclientsfitin",)

    name:   Literal["omniscientalie"]
    config: ConfigOmniscientAlieDecoratorData

    model_config = ConfigDict(extra="forbid")


def forged_update(global_weights, honest_weights, z: float) -> list[np.ndarray]:
    result = []
    for i, w0 in enumerate(global_weights):
        # integer buffers (BatchNorm's num_batches_tracked) are counters, not weights
        if not np.issubdtype(w0.dtype, np.floating):
            result.append(w0)
            continue
        deltas = np.stack([weights[i] for weights in honest_weights]).astype(np.float64) - w0
        result.append((w0 + deltas.mean(axis=0) - z * deltas.std(axis=0)).astype(w0.dtype))
    return result


class OmniscientAlieStrategyDecorator(StrategyDecorator):
    """Robustness tests: the attackers' updates replaced by the omniscient ALIE update."""

    def __init__(self, base_strategy, config):
        super().__init__(base_strategy)
        self.config = config
        self.fabric = pcpc.pybiscus_context.get(pcpc.FABRIC)
        self.global_weights = None

    def configure_fit(self, server_round, parameters, client_manager):
        self.global_weights = parameters_to_ndarrays(parameters)
        return super().configure_fit(server_round, parameters, client_manager)

    def aggregate_fit(self, server_round, results, failures):
        attackers = [res for _, res in results if res.metrics.get("byzantine")]
        honest = [res for _, res in results if not res.metrics.get("byzantine")]
        if server_round < self.config.from_round or not attackers or self.global_weights is None:
            return super().aggregate_fit(server_round, results, failures)
        if len(honest) < 2:
            logm.console.log(f"😈 round {server_round}: omniscient ALIE needs 2 honest updates, {len(honest)} received: no attack")
            return super().aggregate_fit(server_round, results, failures)

        # imported here: the byzantine client plugin is loaded with this one (test manifest), and the
        # same formula keeps the two attacks comparable
        from byzantine.byzantineclient import alie_z
        z = self.config.z if self.config.z is not None else alie_z(len(results), len(attackers))
        forged = forged_update(self.global_weights, [parameters_to_ndarrays(res.parameters) for res in honest], z)
        for res in attackers:
            res.parameters = ndarrays_to_parameters(forged)
        logm.console.log(f"😈 round {server_round}: omniscient ALIE, {len(attackers)} of {len(results)} updates replaced (z={z:.3f})")
        if self.fabric is not None:
            self.fabric.log("alie_z", z, step=server_round)
            self.fabric.log("alie_attackers", len(attackers), step=server_round)
        return super().aggregate_fit(server_round, results, failures)
