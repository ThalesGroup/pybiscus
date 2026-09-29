from collections.abc import Mapping
from enum import Enum
from typing import ClassVar, Optional

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field, model_validator
from torch.utils.data import DataLoader, Dataset, Subset

import pybiscus.core.pybiscus_logger as logm

# Configuration of the train / val / test sets of the data plugins that load official train and
# test splits (cifar10, mnist): where each set comes from, which examples a client uses, how its
# loader reads them. One section per set, each holding everything about that set.
# Kept out of pybiscus.ml.data: the data registry scans every module of that package for plugins.
# pydantic2html names a nested model's fields after its PYBISCUS_CONFIG, not after the field
# holding it: each section declares its own.

# ------------------------------------------------------------------ partition between clients

class PartitionScheme(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    iid = "iid"               # equal shares drawn at random
    dirichlet = "dirichlet"   # each class spread over the clients in proportions drawn from Dirichlet(alpha)
    shards = "shards"         # examples sorted by class, cut in shards, a few shards per client


class ConfigPartitionScheme(BaseModel):
    """how the training data is shared, the same for every client: seed: the same for every client,
    so that the shares are disjoint without any coordination; alpha (dirichlet): the smaller, the
    more each client is dominated by a few classes; min_partition_size (dirichlet): draws are
    repeated until every share has at least this many examples; shards_per_partition (shards):
    classes seen by a client, roughly"""

    scheme: PartitionScheme = PartitionScheme.iid
    seed: int = 42
    alpha: float = Field(default=0.5, gt=0)
    min_partition_size: int = Field(default=10, ge=0)
    shards_per_partition: int = Field(default=2, ge=1)

    model_config = ConfigDict(extra="forbid")


class ConfigPartition(ConfigPartitionScheme):
    """num_partitions: number of clients sharing the training data; partition_id: this client's
    share (0 .. num_partitions - 1); in a session, the manager may set both"""

    num_partitions: int = Field(ge=1)
    partition_id: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _id_in_range(self):
        if self.partition_id >= self.num_partitions:
            raise ValueError(f"partition_id {self.partition_id} must be below num_partitions {self.num_partitions}")
        return self

# ------------------------------------------------------------------ the three sets

class ConfigTrainSet(BaseModel):
    """dir: directory of the official train split; indices: file of the example indices to train on
    (whitespace-separated); partition: this client's share of the examples; seed: order of the
    shuffled batches, reproducible (random if unset)"""

    PYBISCUS_CONFIG: ClassVar[str] = "train"

    dir: str
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = True
    # a tiny last batch destabilizes BatchNorm
    drop_last: bool = True
    seed: Optional[int] = None
    indices: Optional[str] = None
    partition: Optional[ConfigPartition] = None
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _one_selection(self):
        if self.indices and self.partition is not None:
            raise ValueError("train.indices and train.partition both choose the training examples: keep one")
        return self


class ValSource(str, Enum):
    official = "official"   # the official test split: then no data is held out
    holdout = "holdout"     # a fraction of the client's training examples
    indices = "indices"     # the examples listed in the indices file


class ConfigValSet(BaseModel):
    """source: where the validation examples come from; dir: directory of the official test
    split (official); fraction and seed: share and draw of the held-out examples (holdout);
    indices: file of the example indices (indices)"""

    PYBISCUS_CONFIG: ClassVar[str] = "val"

    source: ValSource = ValSource.official
    dir: str
    fraction: float = Field(default=0.1, gt=0, lt=1)
    seed: int = 42
    indices: Optional[str] = None
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = False
    # every example is evaluated: dropping the last batch skipped some of them
    drop_last: bool = False
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _indices_file(self):
        if self.source == ValSource.indices and not self.indices:
            raise ValueError("val.source = indices needs val.indices")
        return self


class ConfigTestSet(BaseModel):
    """dir: directory of the official test split"""

    PYBISCUS_CONFIG: ClassVar[str] = "test"

    dir: str
    batch_size: int = Field(default=32, ge=1)
    shuffle: bool = False
    drop_last: bool = False
    max_samples: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


# the configurations written before the sections: say where each field went, instead of a bare
# "extra inputs are not permitted"
FORMER_FIELDS = {
    "dir_train": "train.dir",
    "dir_val": "val.dir",
    "dir_test": "test.dir",
    "batch_size": "train.batch_size / val.batch_size / test.batch_size",
    "data_train_indices_path": "train.indices",
    "data_val_indices_path": "val.source: indices + val.indices",
    "loaders": "shuffle / drop_last / batch_size / seed of each section",
    "split": "val.source / val.fraction / val.indices",
    "partition": "train.partition",
}


def reject_former_fields(data, former_fields: Mapping[str, str] = FORMER_FIELDS):
    # a Mapping, not only a dict: the CLI validates OmegaConf DictConfig objects
    if isinstance(data, Mapping):
        former = [f"{name} → {former_fields[name]}" for name in data if name in former_fields]
        if former:
            raise ValueError("the data configuration is now grouped in train / val / test sections: " + "; ".join(former))
    return data

# ------------------------------------------------------------------ building the sets

def read_indices(path: str) -> np.ndarray:
    with open(path, encoding="utf-8") as f:
        return np.array([int(token) for token in f.read().split()], dtype=np.int64)


def labels_of(dataset: Dataset) -> np.ndarray:
    # torchvision data sets expose their labels; a plugin whose data set does not can add .targets
    targets = getattr(dataset, "targets", None)
    if targets is None:
        raise ValueError(f"{type(dataset).__name__} exposes no labels (.targets): only the iid partition applies")
    return np.asarray(targets)


def _dirichlet(labels: np.ndarray, p: ConfigPartition, rng) -> list[np.ndarray]:
    # a draw may leave a share almost empty: drawn again, a bounded number of times
    for _ in range(100):
        shares = [[] for _ in range(p.num_partitions)]
        for label in np.unique(labels):
            members = rng.permutation(np.flatnonzero(labels == label))
            proportions = rng.dirichlet(np.full(p.num_partitions, p.alpha))
            cuts = (np.cumsum(proportions)[:-1] * len(members)).astype(int)
            for share, part in zip(shares, np.split(members, cuts)):
                share.extend(part.tolist())
        if min(len(share) for share in shares) >= p.min_partition_size:
            return [np.sort(np.array(share, dtype=np.int64)) for share in shares]
    raise ValueError(f"dirichlet partition: no draw gave every share {p.min_partition_size} examples "
                     f"(alpha {p.alpha}, {p.num_partitions} partitions): raise alpha or lower min_partition_size")


def _shards(labels: np.ndarray, p: ConfigPartition, rng) -> list[np.ndarray]:
    n_shards = p.num_partitions * p.shards_per_partition
    if n_shards > len(labels):
        raise ValueError(f"shards partition: {n_shards} shards for {len(labels)} examples")
    # shuffled before the stable sort: the order within a class is random, not the storage one
    shuffled = rng.permutation(len(labels))
    by_class = shuffled[np.argsort(labels[shuffled], kind="stable")]
    shards = np.array_split(by_class, n_shards)
    order = rng.permutation(n_shards)
    return [np.sort(np.concatenate([shards[k] for k in order[i::p.num_partitions]])) for i in range(p.num_partitions)]


def all_partitions(train_full: Dataset, p: ConfigPartition) -> list[np.ndarray]:
    # a Generator with an explicit seed draws the same shares on every machine
    rng = np.random.default_rng(p.seed)
    if p.scheme == PartitionScheme.iid:
        return np.array_split(rng.permutation(len(train_full)), p.num_partitions)
    labels = labels_of(train_full)
    return (_dirichlet if p.scheme == PartitionScheme.dirichlet else _shards)(labels, p, rng)


def holdout(indices: np.ndarray, fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    shuffled = np.random.default_rng(seed).permutation(indices)
    n_val = max(1, round(len(shuffled) * fraction))
    return np.sort(shuffled[n_val:]), np.sort(shuffled[:n_val])


def split_indices(train_full: Dataset, train: ConfigTrainSet, val: ConfigValSet) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """indices of the training and validation examples in the official train split; None: all of
    them for training, the official test split for validation"""

    # other plugins' sections have no indices file, and a val without source is not drawn from train
    train_indices = getattr(train, "indices", None)
    if train_indices:
        base = read_indices(train_indices)
    elif train.partition is not None:
        base = all_partitions(train_full, train.partition)[train.partition.partition_id]
    else:
        base = None

    if val is None or getattr(val, "source", ValSource.official) == ValSource.official:
        return base, None
    pool = np.arange(len(train_full)) if base is None else base
    if val.source == ValSource.holdout:
        return holdout(pool, val.fraction, val.seed)
    val_idx = read_indices(val.indices)
    # without a train indices file, the validation examples are removed from the training ones
    return (base if train_indices else np.setdiff1d(pool, val_idx)), val_idx


def train_and_val_sets(train_full: Dataset, official_val, train: ConfigTrainSet, val: ConfigValSet) -> tuple[Dataset, Dataset]:
    """official_val: a callable returning the official test split, loaded only when used"""

    train_idx, val_idx = split_indices(train_full, train, val)
    train_set = limit(train_full if train_idx is None else Subset(train_full, np.asarray(train_idx).tolist()), train.max_samples)
    val_set = limit(official_val() if val_idx is None else Subset(train_full, val_idx.tolist()), val.max_samples)
    partition = train.partition
    logm.console.log(f"data: {len(train_set)} training examples, {len(val_set)} validation examples "
                     f"(validation: {val.source.value}"
                     + (f", partition {partition.partition_id + 1}/{partition.num_partitions} {partition.scheme.value}" if partition else "") + ")")
    return train_set, val_set


def limit(dataset: Dataset, max_samples: Optional[int]) -> Dataset:
    """at most max_samples examples, the same on every run (drawn with a fixed seed, kept in order)"""

    if max_samples is None or max_samples >= len(dataset):
        return dataset
    kept = np.sort(np.random.default_rng(0).permutation(len(dataset))[:max_samples])
    return Subset(dataset, kept.tolist())


def partition_subset(dataset: Dataset, partition: Optional[ConfigPartition]) -> Dataset:
    if partition is None:
        return dataset
    return Subset(dataset, all_partitions(dataset, partition)[partition.partition_id].tolist())


def make_loader(dataset: Dataset, options, num_workers: int = 0, order_seed: Optional[int] = None) -> DataLoader:
    """order_seed: reproducible order of the shuffled batches (train's seed; a val seed may mean
    something else, such as cifar's holdout draw)"""

    generator = None
    if options.shuffle and order_seed is not None:
        generator = torch.Generator().manual_seed(order_seed)
    return DataLoader(
        dataset,
        batch_size=options.batch_size,
        num_workers=num_workers,
        shuffle=options.shuffle,
        drop_last=options.drop_last,
        generator=generator,
    )
