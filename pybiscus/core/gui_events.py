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
    # no square brackets: rich reads "[gui]" as a markup tag and removed it from the console output
    logm.console.log(f"📈 gui phase={phase} round={round_text} metric={name} value={value:.6g}")


def log_metric_diff(diff: float) -> None:
    logm.console.log(f"📊⚖️📊 = 🧐🔢 metric diff is {diff:.4f}")


def log_no_evaluation_metric(server_round: int) -> None:
    # a session of relays (they hold no data) gets no federated evaluation: the page says why its
    # panel stays empty
    logm.console.log(f"📊⚖️📊 = 🧐🔢 metric is None 🈚🕳️ gui no_evaluation round={server_round}")


def log_link_event(event: str, server_round: int, examples: Optional[int] = None) -> None:
    """a lower level's round as its link to the upper level sees it: model_received (its clients
    start), aggregate (sent up, with its examples) or failed"""
    tail = "" if examples is None else f" examples={examples}"
    logm.console.log(f"🔗 gui link={event} round={server_round}{tail}")


def log_stop_requested(reason: str, server_round: int) -> None:
    end = f"after round {server_round}" if server_round else "before its first round"
    logm.console.log(f"🛑 gui stop_requested round={server_round}: {reason}, the session ends {end}")


def log_rounds_done(rounds_done: int, num_rounds: int) -> None:
    """with a schedule, the rounds run so far: Flower's round numbers also count the skipped ones"""
    logm.console.log(f"🗓️ gui rounds_done={rounds_done}/{num_rounds}")


def log_session_end(rounds_done: int, num_rounds: int, reason: Optional[str]) -> None:
    if reason is None:
        logm.console.log(f"🏁 gui session_end rounds={rounds_done}/{num_rounds}")
    else:
        logm.console.log(f"🛑 gui session_end rounds={rounds_done}/{num_rounds} stopped: {reason}")


def gui_log_patterns() -> dict[str, str]:
    # JavaScript RegExp sources, compiled as is by the manager page (also valid Python)
    return {
        # round number, from the aggregation lines ("🔁 Round:3 aggregates using …")
        "round": r"🔁 [rR]ound:\s*(\d+)",
        # main metric of a phase: groups phase, round ("-" if unknown), metric name, value
        "round_metric": r"📈 gui phase=(fit|test|evaluate) round=(\d+|-) metric=(\S+) value=(-?[\d.]+(?:[eE][-+]?\d+)?|nan|inf)",
        # duration of a round (timediffcompute decorator)
        "duration": r"time diff is (\d+(?:\.\d+)?)s",
        # variation of the aggregated evaluation loss (metricdiffcompute decorator)
        "metric_diff": r"metric diff is (\d+(?:\.\d+)?)\s*$",
        # no aggregated evaluation loss (no client evaluated): group round
        "no_evaluation": r"gui no_evaluation round=(\d+)",
        # a lower level's link (log_link_event): groups event, round, examples
        "link": r"🔗 gui link=(model_received|aggregate|failed) round=(\d+)(?: examples=(\d+))?",
        # a stop asked for (StoppableServer.request_stop): group round, the last one run
        "stop_requested": r"gui stop_requested round=(\d+)",
        # end of the rounds: groups rounds done, num_rounds, reason of an early stop
        "session_end": r"gui session_end rounds=(\d+)/(\d+)(?: stopped: (.*))?",
        # with a schedule, the rounds counted (log_rounds_done): groups rounds done, num_rounds
        "rounds_done": r"gui rounds_done=(\d+)/(\d+)",
    }
