import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from flwr.client import Client
from flwr.common import Code, EvaluateIns, EvaluateRes, FitIns, FitRes, Status, ndarrays_to_parameters
from lightning import LightningDataModule
from torch.utils.data import DataLoader, IterableDataset

from pybiscus.core.pybiscusexception import PybiscusValueException

# A data module may receive new examples between rounds (logs of the day, new captures). It then
# defines, beside Lightning's methods:
#   refresh() -> Optional[dict]: reads the data again; by default, without it, setup("fit") again,
#       all of it. An incremental module reads only what is new since its cursor (DataCursor), and
#       may return scalars describing what it read (the range of its cursor), sent with the round's
#       metrics so that the reports tell which data a round trained on.
#   commit_refresh(): the round trained on it: its cursor moves on. Called after a successful fit
#       only: a round that fails leaves its data to the next one.

CURSORS_DIR = Path(".pybiscus-cache/data-cursors")


def count_examples(loader: DataLoader) -> int:

    # FedAvg weights clients by this value; len(loader) counts batches, which skews FedAvg as soon as clients use different batch sizes
    if isinstance(loader.dataset, IterableDataset):
        # its sampler has no length, and a declared __len__ is duplicated across workers
        raise PybiscusValueException(
            f"{type(loader.dataset).__name__} is an IterableDataset: "
            "counting examples for FedAvg weighting is not supported"
        )
    if loader.batch_size is None:
        return sum(len(batch) for batch in loader.batch_sampler)
    if loader.drop_last:
        return len(loader) * loader.batch_size
    return len(loader.sampler)


def count_data(data: LightningDataModule) -> dict[str, int]:
    return {"trainset": count_examples(data.train_dataloader()), "valset": count_examples(data.val_dataloader())}


def refresh_data(data: LightningDataModule) -> dict[str, Any]:
    """the scalars the module describes its new data with"""
    refresh = getattr(data, "refresh", None)
    if refresh is None:
        data.setup(stage="fit")
        return {}
    return refresh() or {}


def commit_refresh(data: LightningDataModule) -> None:
    commit = getattr(data, "commit_refresh", None)
    if commit is not None:
        commit()


class DataCursor:
    """where an incremental data module stopped reading, kept across sessions: a client restarted
    for each scheduled session would otherwise read all its data again. key: one per client and
    module, e.g. the module's name and its data directory"""

    def __init__(self, key: str, base: Path = CURSORS_DIR):
        # a readable file name: the cursors of a machine are looked at, and removed, by hand
        self.path = base / (re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_") + ".json")
        self.staged = None

    def load(self, default=None):
        try:
            return json.loads(self.path.read_text())["cursor"]
        except FileNotFoundError:
            return default

    def stage(self, cursor) -> None:
        """the position after the data just read, saved by commit once the round trained on it"""
        self.staged = cursor

    def commit(self) -> None:
        if self.staged is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # written aside then renamed: a client killed while writing must not lose its position
        with tempfile.NamedTemporaryFile("w", dir=self.path.parent, suffix=".json", delete=False) as tmp:
            json.dump({"cursor": self.staged}, tmp)
        os.replace(tmp.name, self.path)
        self.staged = None


class NoNewData(Exception):
    """raised by a client's fit with no example to train on, or its evaluate with none to evaluate
    on: it withdraws from the round"""


class WithdrawingClient(Client):
    """a fit raising NoNewData answers as a failed fit, which the server leaves out of the round:
    with Flower's legacy transport, an exception would end the client's process"""

    def __init__(self, client: Client):
        self.client = client

    def __getattr__(self, name):
        return getattr(self.client, name)

    def get_properties(self, ins):
        return self.client.get_properties(ins)

    def get_parameters(self, ins):
        return self.client.get_parameters(ins)

    def evaluate(self, ins: EvaluateIns) -> EvaluateRes:
        try:
            return self.client.evaluate(ins)
        except NoNewData as reason:
            # 0 examples answered as a success would make Flower's weighted loss divide by zero
            return EvaluateRes(status=Status(code=Code.EVALUATE_NOT_IMPLEMENTED, message=f"no data: {reason}"),
                               loss=0.0, num_examples=0, metrics={})

    def fit(self, ins: FitIns) -> FitRes:
        try:
            return self.client.fit(ins)
        except NoNewData as reason:
            # Flower has no status for a refusal: any code but OK makes it a failure of the round
            return FitRes(status=Status(code=Code.FIT_NOT_IMPLEMENTED, message=f"no new data: {reason}"),
                          parameters=ndarrays_to_parameters([]), num_examples=0, metrics={})
