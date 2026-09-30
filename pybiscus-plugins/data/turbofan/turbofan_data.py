from typing import Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

import pybiscus.core.pybiscus_logger as logm

# Windows over the cycles of NASA C-MAPSS turbofan engines, the target being the remaining useful
# life (RUL) at the window's last cycle. Adapted from
# https://www.kaggle.com/code/jinsolkwon/rul-predictions-using-pytorch-lstm#1.-Data-Processing

ID_COLUMNS = ["engine_no", "time_in_cycles"]


def read_engines(path: str) -> pd.DataFrame:
    # the file's last two sensors are empty columns
    return pd.read_csv(path, sep=",").dropna(axis=1)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in ID_COLUMNS]


def check_engines(frame: pd.DataFrame, engines: list[int], section: str) -> None:
    missing = sorted(set(engines) - set(frame.engine_no.unique()))
    if missing:
        raise ValueError(f"{section}.engines: engines {missing} are not in the file "
                         f"(available: {sorted(frame.engine_no.unique().tolist())})")


def normalization(frame: pd.DataFrame, engines: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """mean and standard deviation of each feature over these engines' cycles"""

    values = frame[frame.engine_no.isin(engines)][feature_columns(frame)].to_numpy(np.float64)
    std = values.std(axis=0)
    # several sensors are constant in C-MAPSS: dividing by their zero deviation gave NaN
    std[std == 0] = 1.0
    return values.mean(axis=0), std


class TurbofanWindows(Dataset):

    def __init__(self, frame: pd.DataFrame, engines: list[int], window: int,
                 stats: Optional[tuple[np.ndarray, np.ndarray]] = None, rul_clip: Optional[int] = None):
        columns = feature_columns(frame)
        inputs, targets = [], []
        for engine in engines:
            cycles = frame[frame.engine_no == engine].sort_values("time_in_cycles")
            if len(cycles) < window:
                logm.console.log(f"⚠️ turbofan: engine {engine} has {len(cycles)} cycles, fewer than the window ({window}): skipped")
                continue
            values = cycles[columns].to_numpy(np.float64)
            if stats is not None:
                values = (values - stats[0]) / stats[1]
            # 0 at the engine's last cycle
            rul = (len(cycles) - cycles.time_in_cycles.to_numpy()).astype(np.float64)
            if rul_clip is not None:
                rul = np.minimum(rul, rul_clip)
            # windows within the engine: taken over the whole table, one mixed the end of an
            # engine with the start of the next and carried the next one's target
            windows = np.lib.stride_tricks.sliding_window_view(values, window, axis=0)  # (n, features, window)
            inputs.append(windows.transpose(0, 2, 1))
            targets.append(rul[window - 1:])
        n_features = len(columns)
        self.inputs = torch.tensor(np.concatenate(inputs) if inputs else np.empty((0, window, n_features)), dtype=torch.float32)
        self.targets = torch.tensor(np.concatenate(targets) if targets else np.empty(0), dtype=torch.float32)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return self.inputs[idx], self.targets[idx]
