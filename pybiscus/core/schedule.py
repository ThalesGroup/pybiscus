import math
import os
import re
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from enum import Enum
from typing import ClassVar, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cronsim import CronSim, CronSimError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DURATION_UNITS = {"s": 1, "min": 60, "h": 3600, "d": 86400, "w": 604800}
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(s|min|h|d|w)")


def parse_duration(text: str) -> timedelta:
    """"90s", "15min", "1h30min", "1d", "2w"; units s, min, h, d, w"""
    compact = text.replace(" ", "")
    parts = _DURATION_PART.findall(compact)
    # "m" refused: minutes or months, a period misread by a factor of 43 200 would go unnoticed
    if not parts or "".join(value + unit for value, unit in parts) != compact:
        raise ValueError(f"'{text}' is not a duration: a number and a unit (s, min, h, d, w), e.g. 90s, 15min, 1h30min, 1d")
    seconds = sum(float(value) * DURATION_UNITS[unit] for value, unit in parts)
    if seconds <= 0:
        raise ValueError(f"'{text}': a period must be longer than zero")
    return timedelta(seconds=seconds)


def machine_zone() -> tzinfo:
    """the machine's zone by its name, so that its changes of time are known; a fixed offset otherwise"""
    candidates = [os.environ.get("TZ", "").lstrip(":")]
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        candidates.append(str(localtime.resolve()).partition("zoneinfo/")[2])
    for name in candidates:
        if name:
            try:
                return ZoneInfo(name)
            except (ZoneInfoNotFoundError, ValueError):
                pass
    return datetime.now().astimezone().tzinfo


# an Enum, not a Literal: the agent's forms show a Literal as a fixed value, like a plugin's name
class ScheduleStart(str, Enum):
    now = "now"
    deadline = "deadline"


ScheduleStart.PYBISCUS_DESCRIPTIONS = {
    "now": "the first round starts at once",
    "deadline": "the first round waits for the first deadline too",
}


class ConfigSchedule(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "schedule"

    every: Optional[str] = Field(default=None, description=
        "a round every period: a number and a unit (s, min, h, d, w), e.g. 15min, 1h30min, 1d; the deadlines follow "
        "one another from the first one, in elapsed time (a change of time shifts them by an hour: fixed hours are cron's)")
    cron: Optional[str] = Field(default=None, description=
        'a round at fixed times, a cron expression: minute hour day month weekday, e.g. "0 2 * * *" every day at 02:00')
    timezone: Optional[str] = Field(default=None, description=
        "zone of the cron times, e.g. Europe/Paris; the machine's if unset")
    start: ScheduleStart = Field(default=ScheduleStart.now, description=
        "now: the first round starts at once; deadline: it waits for the first deadline too")

    model_config = ConfigDict(extra="forbid")

    # field validators, not one model validator: the error then names its field (loc), which the
    # forms show it under
    @field_validator("every")
    @classmethod
    def valid_period(cls, every):
        if every is not None:
            parse_duration(every)
        return every

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, timezone):
        if timezone is not None:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError(f"unknown zone '{timezone}' (an IANA name, e.g. Europe/Paris)")
        return timezone

    # the syntax of a cron expression does not depend on the zone it is read in
    @field_validator("cron")
    @classmethod
    def valid_cron(cls, cron):
        if cron is not None:
            try:
                next(CronSim(cron, datetime.now()))
            except CronSimError as error:
                raise ValueError(f"'{cron}': {error}")
        return cron

    @model_validator(mode="after")
    def one_format(self):
        if (self.every is None) == (self.cron is None):
            raise ValueError("schedule: give either every (a period) or cron (fixed times), exactly one of them")
        return self

    def zone(self) -> tzinfo:
        return ZoneInfo(self.timezone) if self.timezone else machine_zone()


class Schedule:
    """the deadlines of the rounds; a deadline missed, a round lasting longer than the period, is
    not made up for: the next one is the first still to come"""

    def __init__(self, config: ConfigSchedule):
        self.config = config
        self.zone = config.zone()
        self.period = parse_duration(config.every) if config.every else None
        self.previous: Optional[datetime] = None
        # deadlines passed while the previous round ran, not made up for
        self.skipped = 0

    def now(self) -> datetime:
        return datetime.now(self.zone)

    def next_deadline(self, now: Optional[datetime] = None) -> datetime:
        now = now or self.now()
        self.skipped = 0
        if self.previous is None:
            deadline = now if self.config.start == ScheduleStart.now else self._after(now, now)
        else:
            deadline = self._after(self.previous, now)
        self.previous = deadline
        return deadline

    def _after(self, previous: datetime, now: datetime) -> datetime:
        if self.period is not None:
            # in UTC: python adds a timedelta to an aware datetime on the wall clock, an hour too
            # many or too few across a change of time; fixed hours of the day are cron's job
            previous, now = previous.astimezone(timezone.utc), now.astimezone(timezone.utc)
            steps = 1 if now < previous + self.period else math.floor((now - previous) / self.period) + 1
            self.skipped = steps - 1
            return (previous + steps * self.period).astimezone(self.zone)
        # strictly after both: the deadline just used must not come back
        deadline = next(CronSim(self.config.cron, max(previous, now)))
        self.skipped = sum(1 for _ in _until(CronSim(self.config.cron, previous), now))
        return deadline


def _until(times, end: datetime):
    for time in times:
        if time > end:
            return
        yield time
