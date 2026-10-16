import time
from enum import Enum
from typing import ClassVar, Literal, Optional

from flwr.server.history import History
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.interfaces.flower.stoppingcriterion import StoppingCriterion


# the phases of the manager's charts (gui_events.PHASES)
class MetricSource(str, Enum):
    # an Enum and not a Literal: the agent's form offers an Enum's values, a Literal's first only
    test = "test"
    evaluate = "evaluate"
    fit = "fit"


MetricSource.PYBISCUS_DESCRIPTIONS = {
    "test": "the server's evaluation of the global model on its test set",
    "evaluate": "the clients' evaluation of the global model, aggregated",
    "fit": "the clients' training metrics, aggregated",
}


class MetricGoal(str, Enum):
    maximize = "maximize"
    minimize = "minimize"


MetricGoal.PYBISCUS_DESCRIPTIONS = {
    "maximize": "the higher the better (accuracy, f1score…)",
    "minimize": "the lower the better (loss…)",
}


def metric_series(history: History, source: MetricSource, metric: str) -> Optional[list[tuple[int, float]]]:
    """(round, value) of a metric, None if the source has no such metric"""
    metrics, losses = {
        MetricSource.test: (history.metrics_centralized, history.losses_centralized),
        MetricSource.evaluate: (history.metrics_distributed, history.losses_distributed),
        MetricSource.fit: (history.metrics_distributed_fit, []),
    }[MetricSource(source)]
    if metric in metrics:
        return [(r, float(v)) for r, v in metrics[metric]]
    # the strategies return the loss apart from the other metrics
    if metric == "loss" and losses:
        return [(r, float(v)) for r, v in losses]
    return None


def available_metrics(history: History, source: MetricSource) -> list[str]:
    names = [name for name in ("loss", "accuracy") if metric_series(history, source, name)]
    names += [name for name in {
        MetricSource.test: history.metrics_centralized,
        MetricSource.evaluate: history.metrics_distributed,
        MetricSource.fit: history.metrics_distributed_fit,
    }[MetricSource(source)] if name not in names]
    return names


class MetricCriterion(StoppingCriterion):

    def __init__(self, metric: str, source: MetricSource, goal: MetricGoal):
        self.metric, self.source, self.goal = metric, MetricSource(source), MetricGoal(goal)
        self.warned = False

    def series(self, server_round: int, history: History) -> Optional[list[float]]:
        """the values up to this round, None (with a warning, once) while the round has none: a
        misspelt metric, or no evaluation of that kind, never stops the session"""
        series = metric_series(history, self.source, self.metric)
        if series and series[-1][0] == server_round:
            return [value for _, value in series]
        if not self.warned:
            self.warned = True
            logm.console.log(f"⚠️ stopping criterion {type(self).__name__}: no {self.source.value} metric "
                             f"'{self.metric}' at round {server_round} (available: {', '.join(available_metrics(history, self.source)) or 'none'})")
        return None

    def best(self, values: list[float]) -> float:
        return max(values) if self.goal == MetricGoal.maximize else min(values)


# ................................................................................... threshold

class ConfigMetricThresholdData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    metric: str = Field(default="accuracy", description="name of the metric, as the strategy reports it (accuracy, loss, f1score…)")
    source: MetricSource = Field(default=MetricSource.test, description="which evaluation the metric comes from")
    goal: MetricGoal = Field(default=MetricGoal.maximize, description="maximize: stop once the metric reaches the value or more; minimize: the value or less")
    value: float = Field(description="the value to reach")

    model_config = ConfigDict(extra="forbid")


class ConfigMetricThreshold(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Metric threshold"

    name: Literal["threshold"]
    config: ConfigMetricThresholdData

    model_config = ConfigDict(extra="forbid")


class MetricThreshold(MetricCriterion):
    """Ends the session once a metric reaches a value (an accuracy of 0.98, a loss of 0.05)."""

    def __init__(self, metric: str, source: MetricSource, goal: MetricGoal, value: float):
        super().__init__(metric, source, goal)
        self.value = value

    def should_stop(self, server_round: int, history: History) -> Optional[str]:
        values = self.series(server_round, history)
        if values is None:
            return None
        current = values[-1]
        reached = current >= self.value if self.goal == MetricGoal.maximize else current <= self.value
        sign = "≥" if self.goal == MetricGoal.maximize else "≤"
        return f"{self.source.value} {self.metric} {current:.4g} {sign} {self.value:g}" if reached else None


# .................................................................................... patience

class ConfigMetricPatienceData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    metric: str = Field(default="loss", description="name of the metric, as the strategy reports it (accuracy, loss, f1score…)")
    source: MetricSource = Field(default=MetricSource.test, description="which evaluation the metric comes from")
    goal: MetricGoal = Field(default=MetricGoal.minimize, description="whether the metric improves by going up or down")
    patience: int = Field(default=3, ge=1, description="rounds without improvement before the session ends")
    min_delta: float = Field(default=0.0, ge=0, description="a change of the best value smaller than this is no improvement")

    model_config = ConfigDict(extra="forbid")


class ConfigMetricPatience(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Metric patience"

    name: Literal["patience"]
    config: ConfigMetricPatienceData

    model_config = ConfigDict(extra="forbid")


class MetricPatience(MetricCriterion):
    """Ends the session when a metric has not improved for a number of rounds (early stopping)."""

    def __init__(self, metric: str, source: MetricSource, goal: MetricGoal, patience: int, min_delta: float):
        super().__init__(metric, source, goal)
        self.patience, self.min_delta = patience, min_delta

    def should_stop(self, server_round: int, history: History) -> Optional[str]:
        values = self.series(server_round, history)
        if values is None or len(values) <= self.patience:
            return None
        best, recent_best = self.best(values[:-self.patience]), self.best(values[-self.patience:])
        gain = recent_best - best if self.goal == MetricGoal.maximize else best - recent_best
        if gain > self.min_delta:
            return None
        return (f"{self.source.value} {self.metric}: no improvement over {self.min_delta:g} in {self.patience} "
                f"round{'s' if self.patience > 1 else ''} (best {best:.4g}, since then {recent_best:.4g})")


# ................................................................................ max duration

class ConfigMaxDurationData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    minutes: float = Field(gt=0, description="duration of the rounds after which the session ends, from the start of the first one; tested at the end of each round, which is finished")

    model_config = ConfigDict(extra="forbid")


class ConfigMaxDuration(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Maximal duration"

    name: Literal["maxduration"]
    config: ConfigMaxDurationData

    model_config = ConfigDict(extra="forbid")


class MaxDuration(StoppingCriterion):
    """Ends the session after a duration: the round under way when it is over is finished."""

    def __init__(self, minutes: float):
        self.minutes = minutes
        self.started = None

    def start(self) -> None:
        self.started = time.monotonic()

    def should_stop(self, server_round: int, history: History) -> Optional[str]:
        elapsed = (time.monotonic() - self.started) / 60
        return f"{elapsed:.1f} min of rounds ≥ {self.minutes:g} min" if elapsed >= self.minutes else None
