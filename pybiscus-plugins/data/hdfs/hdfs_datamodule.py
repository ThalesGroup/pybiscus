import csv
from typing import Optional

import lightning.pytorch as pl
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

import pybiscus.core.pybiscus_logger as logm
from pybiscus.ml.datasplit import ConfigPartition, all_partitions, holdout, limit, make_loader, reject_former_fields

from hdfs.hdfs_dataconfig import (
    HDFS_FORMER_FIELDS, HdfsTestFormat, HdfsTestSet, HdfsTrainSet, HdfsValSet, HdfsValSource,
)


def read_sequences(path: str) -> list[tuple[int, ...]]:
    """one sequence of event ids per line, shifted to start at 0"""
    with open(path, newline="") as f:
        return [tuple(int(event) - 1 for event in row) for row in csv.reader(f) if row]


class HDFSWindows(Dataset):
    """every window of `window` events of the sequences, with the event that follows it"""

    def __init__(self, sequences, window):
        inputs, targets = [], []
        for sequence in sequences:
            for i in range(len(sequence) - window):
                inputs.append(sequence[i:i + window])
                targets.append(sequence[i + window])
        # (N, window, 1): Deeplog's input has one channel
        self.inputs = torch.tensor(inputs, dtype=torch.float).reshape(len(inputs), window, 1)
        self.targets = torch.tensor(targets, dtype=torch.long)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return self.inputs[idx], self.targets[idx]


class HDFSSessions(Dataset):
    """labelled sessions (CSV "seq,label"), each distinct sequence once with its count: Deeplog
    flags a session as soon as one of its events is not among the predicted candidates"""

    def __init__(self, path, window):
        counts, labels = {}, {}
        for _, row in pd.read_csv(path).iterrows():
            events = [int(n) - 1 for n in str(row["seq"]).split(",")]
            # a session shorter than the window is padded to one window and its next event
            events += [-1] * (window + 1 - len(events))
            key = tuple(events)
            counts[key] = counts.get(key, 0) + 1
            labels[key] = int(row["label"])
        sequences = list(counts)
        width = max(len(sequence) for sequence in sequences)
        # -99 marks the end of a session in the padded batch (Deeplog stops there)
        self.sequences = torch.tensor([list(s) + [-99] * (width - len(s)) for s in sequences], dtype=torch.float)
        self.counts = [counts[s] for s in sequences]
        self.labels = [labels[s] for s in sequences]

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], (self.counts[idx], self.labels[idx])


class HDFSDataModule(pl.LightningDataModule):

    def __init__(self, window: int = 10, train=None, val=None, test=None, num_workers: int = 0, **former_fields):
        super().__init__()
        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields, HDFS_FORMER_FIELDS)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.window = window
        self.train = HdfsTrainSet.model_validate(train or {})
        self.val = HdfsValSet.model_validate(val or {})
        self.test = HdfsTestSet.model_validate(test or {})
        self.num_workers = num_workers
        self.data_train = self.data_val = self.data_test = None

    def train_source(self):
        """the training sequences, which the partitions and holdout share out"""
        return read_sequences(self.train.file)

    def split_units(self, partition: Optional[ConfigPartition]) -> tuple[np.ndarray, Optional[np.ndarray]]:
        """indices of the training and (holdout) validation sequences of a partition"""
        sequences = self.train_source()
        base = np.arange(len(sequences)) if partition is None else all_partitions(sequences, partition)[partition.partition_id]
        if self.val.source == HdfsValSource.holdout:
            return holdout(base, self.val.fraction, self.val.seed)
        return np.sort(base), None

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            sequences = self.train_source()
            train_idx, val_idx = self.split_units(self.train.partition)
            self.data_train = limit(HDFSWindows([sequences[i] for i in train_idx], self.window), self.train.max_samples)
            val_sequences = [sequences[i] for i in val_idx] if val_idx is not None else read_sequences(self.val.file)
            self.data_val = limit(HDFSWindows(val_sequences, self.window), self.val.max_samples)
            partition = self.train.partition
            logm.console.log(
                f"hdfs: {len(train_idx)} training sequences ({len(self.data_train)} windows), "
                f"{len(val_sequences)} validation sequences ({len(self.data_val)} windows, {self.val.source.value})"
                + (f", partition {partition.partition_id + 1}/{partition.num_partitions}" if partition else "")
            )
        if stage == "test" or stage is None:
            if not self.test.file:
                raise ValueError("hdfs: test.file is required to test (the server's data section)")
            if self.test.format == HdfsTestFormat.sessions:
                self.data_test = HDFSSessions(self.test.file, self.window)
                logm.console.log(f"hdfs: {len(self.data_test)} distinct test sessions ({sum(self.data_test.counts)} in all)")
            else:
                self.data_test = limit(HDFSWindows(read_sequences(self.test.file), self.window), self.test.max_samples)
                logm.console.log(f"hdfs: {len(self.data_test)} test windows")

    def train_dataloader(self) -> DataLoader:
        return make_loader(self.data_train, self.train, self.num_workers, order_seed=self.train.seed)

    def val_dataloader(self) -> DataLoader:
        return make_loader(self.data_val, self.val, self.num_workers)

    def test_dataloader(self) -> DataLoader:
        if self.test.format == HdfsTestFormat.sessions:
            # Deeplog's F1 is computed per batch: right only with every session in one batch
            return DataLoader(self.data_test, batch_size=len(self.data_test), shuffle=False, num_workers=self.num_workers)
        return make_loader(self.data_test, self.test, self.num_workers)
