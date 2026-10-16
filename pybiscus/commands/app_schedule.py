from typing import Annotated, Optional

import typer
from pydantic import ValidationError

import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.schedule import ConfigSchedule, Schedule, ScheduleStart

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")


@app.command()
def preview(
    every:    Annotated[Optional[str], typer.Option(help="a period: 90s, 15min, 1h30min, 1d, 2w")] = None,
    cron:     Annotated[Optional[str], typer.Option(help='fixed times: "minute hour day month weekday", e.g. "0 2 * * *"')] = None,
    timezone: Annotated[Optional[str], typer.Option(help="zone of the cron times, e.g. Europe/Paris; the machine's if unset")] = None,
    start:    Annotated[ScheduleStart, typer.Option(help="now: the first round at once; deadline: at the first deadline")] = ScheduleStart.now,
    count:    Annotated[int, typer.Option(min=1, help="deadlines shown")] = 5,
) -> None:
    """The next deadlines of a schedule, to check it before a session."""
    try:
        config = ConfigSchedule(every=every, cron=cron, timezone=timezone, start=start)
    except ValidationError as error:
        logm.console.log(f"❌ {error.errors()[0]['msg']}")
        raise typer.Exit(code=1)
    schedule = Schedule(config)
    logm.console.log(f"🗓️ zone {schedule.zone}")
    deadline = schedule.next_deadline()
    for _ in range(count):
        logm.console.log(f"  {deadline.isoformat(sep=' ', timespec='seconds')}")
        deadline = schedule.next_deadline(deadline)
