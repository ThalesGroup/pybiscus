from enum import Enum
from typing import ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.clientfactory import ClientFactory

# A malicious (byzantine) client, to test the robust aggregations: it trains as an honest one, then
# alters what it sends. Declared in launch/campaign/test-plugins-conf.yml only, never in the
# default manifest: it must not appear in a real session's forms.


class ByzantineAttack(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    none = "none"              # the honest update (num_examples_factor may still lie)
    sign_flip = "sign_flip"    # w_global - scale * delta: pulls the model the wrong way
    scale = "scale"            # w_global + scale * delta: dominates the aggregate
    gaussian = "gaussian"      # w_global + N(0, stddev): a faulty or random client


class ConfigByzantineClientData(BaseModel):
    """attack applied to the update delta = w_trained - w_global from round from_round on;
    num_examples_factor: the reported number of examples is multiplied (FedAvg weighs by it)"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    attack: ByzantineAttack = ByzantineAttack.sign_flip
    scale: float = Field(default=10.0, gt=0)
    stddev: float = Field(default=1.0, gt=0)
    num_examples_factor: float = Field(default=1.0, gt=0)
    seed: int = 0
    from_round: int = Field(default=1, ge=1)

    model_config = ConfigDict(extra="forbid")


class ConfigByzantineClient(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Byzantine (robustness tests)"

    name:   Literal["byzantine"]
    config: ConfigByzantineClientData

    model_config = ConfigDict(extra="forbid")


def attacked(global_weights, trained_weights, conf: ConfigByzantineClientData, rng) -> list[np.ndarray]:
    result = []
    for w0, w in zip(global_weights, trained_weights):
        # integer buffers (BatchNorm's num_batches_tracked) are counters, not weights
        if not np.issubdtype(w.dtype, np.floating):
            result.append(w)
            continue
        delta = w - w0
        if conf.attack == ByzantineAttack.sign_flip:
            w = w0 - conf.scale * delta
        elif conf.attack == ByzantineAttack.scale:
            w = w0 + conf.scale * delta
        elif conf.attack == ByzantineAttack.gaussian:
            w = w0 + rng.normal(0.0, conf.stddev, size=w.shape)
        result.append(w.astype(w0.dtype, copy=False))
    return result


def byzantine_client_class():
    # imported here, not at the top: the server loads the plugins while it imports
    # FlowerFabricClient's module, and a top-level import of it came back partially initialized
    from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclient import FlowerFabricClient

    class ByzantineClient(FlowerFabricClient):

        def __init__(self, byzantine: ConfigByzantineClientData, **kwargs):
            super().__init__(**kwargs)
            self.byzantine = byzantine

        def fit(self, parameters, config):
            trained, num_examples, metrics = super().fit(parameters, config)
            server_round = int(config["server_round"])
            # visible in the server's per-client fit metrics
            metrics["byzantine"] = 1
            if server_round < self.byzantine.from_round:
                return trained, num_examples, metrics
            rng = np.random.default_rng(self.byzantine.seed + server_round)
            trained = attacked(parameters, trained, self.byzantine, rng)
            num_examples = int(round(num_examples * self.byzantine.num_examples_factor))
            logm.console.log(f"😈 round {server_round}: {self.byzantine.attack.value} attack, {num_examples} examples reported")
            return trained, num_examples, metrics

    return ByzantineClient


class ByzantineClientFactory(ClientFactory):

    def __init__(self, config, data, model, num_examples):
        self.config = config
        self.data = data
        self.model = model
        self.num_examples = num_examples

    def get_client(self):
        return byzantine_client_class()(
            byzantine=self.config.flower_client.alternate_client_class.config,
            cid=self.config.client_run.cid,
            model=self.model,
            data=self.data,
            num_examples=self.num_examples,
            conf_fabric=self.config.client_compute_context.hardware,
            pre_train_val=self.config.client_run.pre_train_val,
            optimizer_state=self.config.client_run.optimizer_state,
        )
