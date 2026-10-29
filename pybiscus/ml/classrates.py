import re
from typing import Mapping

import torch

# per-class counts divided by the batch's size: averaged over the examples (BatchMean, then Flower's
# mean weighted by the clients' examples) they stay the counts of the whole data divided by its size,
# whose ratios give an exact F1, which a mean of per-batch or per-site F1 does not
RATE_PREFIX = "rate_"
_COUNT_KEY = re.compile(rf"^{RATE_PREFIX}(tp|fp|fn)_(\d+)$")
_CONFUSION_KEY = re.compile(rf"^{RATE_PREFIX}cm_(\d+)_(\d+)$")


def class_rate_keys(num_classes: int, confusion_matrix: bool = False) -> list[str]:
    keys = [f"{RATE_PREFIX}{kind}_{c}" for c in range(num_classes) for kind in ("tp", "fp", "fn")]
    if confusion_matrix:
        keys += [f"{RATE_PREFIX}cm_{t}_{p}" for t in range(num_classes) for p in range(num_classes)]
    return keys


def class_rates(predicted: torch.Tensor, targets: torch.Tensor, num_classes: int,
                confusion_matrix: bool = False) -> dict[str, torch.Tensor]:
    predicted, targets = predicted.reshape(-1).long(), targets.reshape(-1).long()
    size = max(1, targets.numel())
    # an out-of-range label would silently land in another cell of the bincount
    if targets.numel() and (targets.min() < 0 or targets.max() >= num_classes
                            or predicted.min() < 0 or predicted.max() >= num_classes):
        raise ValueError(f"class_rates: a label or a prediction outside 0..{num_classes - 1}")
    matrix = torch.bincount(targets * num_classes + predicted, minlength=num_classes ** 2).reshape(num_classes, num_classes)
    matrix = matrix.to(torch.float32) / size
    tp = matrix.diagonal()
    fp, fn = matrix.sum(dim=0) - tp, matrix.sum(dim=1) - tp
    rates = {}
    for c in range(num_classes):
        rates[f"{RATE_PREFIX}tp_{c}"], rates[f"{RATE_PREFIX}fp_{c}"], rates[f"{RATE_PREFIX}fn_{c}"] = tp[c], fp[c], fn[c]
    if confusion_matrix:
        for t in range(num_classes):
            for p in range(num_classes):
                rates[f"{RATE_PREFIX}cm_{t}_{p}"] = matrix[t, p]
    return rates


def per_class_scores(metrics: Mapping[str, object]) -> dict[int, dict[str, float]]:
    counts: dict[int, dict[str, float]] = {}
    for key, value in metrics.items():
        match = _COUNT_KEY.match(key)
        if match and isinstance(value, (int, float)):
            counts.setdefault(int(match[2]), {})[match[1]] = float(value)
    scores = {}
    for c, count in sorted(counts.items()):
        if len(count) < 3:
            continue
        tp, fp, fn = count["tp"], count["fp"], count["fn"]
        # scikit-learn's zero_division=0, and a class neither present nor predicted left out of the macro mean
        scores[c] = {"support": tp + fn,
                     "precision": tp / (tp + fp) if tp + fp > 0 else 0.0,
                     "recall": tp / (tp + fn) if tp + fn > 0 else 0.0,
                     "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn > 0 else 0.0,
                     "seen": tp + fp + fn > 0}
    return scores


def with_derived_metrics(metrics: dict) -> dict:
    """adds f1_macro when the metrics hold per-class rates; recomputed from the rates, never averaged"""
    scores = per_class_scores(metrics)
    seen = [score for score in scores.values() if score["seen"]]
    if seen:
        metrics["f1_macro"] = sum(score["f1"] for score in seen) / len(seen)
    return metrics


def confusion_matrix_of(metrics: Mapping[str, object]) -> list[list[float]]:
    cells = {(int(m[1]), int(m[2])): float(v) for k, v in metrics.items()
             if (m := _CONFUSION_KEY.match(k)) and isinstance(v, (int, float))}
    if not cells:
        return []
    n = 1 + max(max(t, p) for t, p in cells)
    return [[cells.get((t, p), 0.0) for p in range(n)] for t in range(n)]
