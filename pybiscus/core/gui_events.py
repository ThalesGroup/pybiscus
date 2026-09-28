# The session manager's GUI charts runs by matching regular expressions against server logs.
# They hard-coded 'accuracy', so the charts stayed empty for other models (LSTM, linear
# regression: loss only; Deeplog: f1score). Lines and patterns are defined here, together.

import math
from numbers import Real
from typing import Mapping, Optional

import pybiscus.core.pybiscus_logger as logm

# a model may name the metric to chart; otherwise the first non-loss metric of its signature
MAIN_METRIC_ATTRIBUTE = "PYBISCUS_MAIN_METRIC"

PHASES = ("fit", "test", "evaluate")

_main_metric: Optional[str] = None


def main_metric_for_model(model) -> str:
    declared = getattr(model, MAIN_METRIC_ATTRIBUTE, None)
    if declared:
        return declared
    from pybiscus.ml.loops_fabric import signature_of_mode
    try:
        keys = list(signature_of_mode(model, "test").__annotations__)
    except AttributeError:
        return "loss"
    return next((k for k in keys if k != "loss"), "loss")


def set_main_metric(name: Optional[str]) -> None:
    global _main_metric
    _main_metric = name


def _is_charted(key: str) -> bool:
    # bookkeeping and derived keys: client id, per-epoch copies, pre-training validation
    return not (key == "cid" or "_epoch_" in key or key.endswith("_pre_train_val"))


def select_main_metric(metrics: Mapping[str, object]) -> Optional[tuple[str, float]]:
    numeric = {k: float(v) for k, v in metrics.items()
               if _is_charted(k) and isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(float(v))}
    if _main_metric in numeric:
        return _main_metric, numeric[_main_metric]
    name = next((k for k in numeric if k != "loss"), "loss" if "loss" in numeric else None)
    return (name, numeric[name]) if name else None


def log_round_metric(phase: str, metrics: Mapping[str, object], server_round: Optional[int] = None) -> None:
    selected = select_main_metric(metrics)
    if selected is None:
        return
    name, value = selected
    round_text = "-" if server_round is None else str(server_round)
    logm.console.log(f"📈 [gui] phase={phase} round={round_text} metric={name} value={value:.6g}")


def gui_log_patterns() -> dict[str, str]:
    # JavaScript RegExp sources, compiled as is by the manager page (also valid Python)
    return {
        # round number, from the aggregation lines ("🔁 Round:3 aggregates using …")
        "round": r"🔁 [rR]ound:\s*(\d+)",
        # main metric of a phase: groups phase, round ("-" if unknown), metric name, value
        "round_metric": r"📈 \[gui\] phase=(fit|test|evaluate) round=(\d+|-) metric=(\S+) value=(-?[\d.]+(?:[eE][-+]?\d+)?|nan|inf)",
        # duration of a round (timediffcompute decorator)
        "duration": r"time diff is (\d+(?:\.\d+)?)s",
        # variation of the aggregated evaluation loss (metricdiffcompute decorator)
        "metric_diff": r"metric diff is (\d+(?:\.\d+)?)\s*$",
    }
