import math
import time
from enum import Enum
from pathlib import Path
from statistics import NormalDist
from typing import ClassVar, Literal, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # "A Little Is Enough" (Baruch et al., 2019): colluders pool their honest updates and all send
    # mean - z * std, close enough to pass the robust aggregations, biased the same way every round
    alie = "alie"


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
    # alie: number of colluding attackers (at least 2 to estimate a deviation), total number of
    # clients (sets z), z itself to force it, directory they share, wait for the others
    colluders: int = Field(default=2, ge=2)
    num_clients: Optional[int] = Field(default=None, ge=1)
    z: Optional[float] = Field(default=None, gt=0)
    shared_dir: str = "/tmp/pybiscus-alie"
    timeout: float = Field(default=120.0, gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _alie_z(self):
        if self.attack == ByzantineAttack.alie and self.z is None and self.num_clients is None:
            raise ValueError("byzantine alie: set num_clients (z is computed from it) or z")
        return self


class ConfigByzantineClient(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Byzantine (robustness tests)"

    name:   Literal["byzantine"]
    config: ConfigByzantineClientData

    model_config = ConfigDict(extra="forbid")


def alie_z(num_clients: int, colluders: int) -> float:
    """the largest deviation that still passes for honest (Baruch et al., 2019): s clients must
    be outvoted, s = floor(n / 2 + 1) - m, z = inverse normal CDF of (n - s) / n"""
    s = math.floor(num_clients / 2 + 1) - colluders
    return NormalDist().inv_cdf((num_clients - s) / num_clients)


def alie_update(global_weights, trained_weights, conf: ConfigByzantineClientData, cid: str, server_round: int):
    """the colluders' common update, None if they did not all show up in time"""
    deltas = [w - w0 for w, w0 in zip(trained_weights, global_weights)]
    round_dir = Path(conf.shared_dir) / f"round_{server_round}"
    round_dir.mkdir(parents=True, exist_ok=True)
    # written under another name then renamed: the others never read a half-written file (through a
    # file object: given a path, np.savez appends ".npz", which the glob below would count)
    tmp = round_dir / f"{cid}.part"
    with open(tmp, "wb") as f:
        np.savez(f, *deltas)
    tmp.rename(round_dir / f"{cid}.npz")
    deadline = time.monotonic() + conf.timeout
    while len(files := sorted(round_dir.glob("*.npz"))) < conf.colluders:
        if time.monotonic() > deadline:
            return None
        time.sleep(0.2)
    pooled = [np.load(f) for f in files[:conf.colluders]]
    z = conf.z if conf.z is not None else alie_z(conf.num_clients, conf.colluders)
    result = []
    for i, (w0, w) in enumerate(zip(global_weights, trained_weights)):
        if not np.issubdtype(w.dtype, np.floating):
            result.append(w)
            continue
        stacked = np.stack([p[f"arr_{i}"] for p in pooled]).astype(np.float64)
        result.append((w0 + stacked.mean(axis=0) - z * stacked.std(axis=0)).astype(w0.dtype))
    return result


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
            if self.byzantine.attack == ByzantineAttack.alie:
                common = alie_update(parameters, trained, self.byzantine, str(self.cid), server_round)
                if common is None:
                    logm.console.log(f"😈 round {server_round}: the other colluders did not show up, honest update sent")
                    return trained, num_examples, metrics
                trained = common
            else:
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
