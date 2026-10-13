import re
import time
from threading import Lock

from pybiscus.core.gui_events import gui_log_patterns

# The rounds of this manager's session, read from its server's log lines as they arrive: sent up in
# its topology, an upper level charts where each level spends a round. Only durations leave the
# manager: the clocks of two sites are never compared.

_PATTERNS = {name: re.compile(gui_log_patterns()[name]) for name in ("round_metric", "link")}
_lock = Lock()
_rounds = {}   # round -> {"test_at", "model_at", "aggregate_at", "examples", "failed"}


def note_server_line(message: str) -> None:
    now = time.time()
    metric = _PATTERNS["round_metric"].search(message)
    if metric:
        if metric.group(1) == "test" and metric.group(2) != "-":
            with _lock:
                _rounds.setdefault(int(metric.group(2)), {})["test_at"] = now
        return
    link = _PATTERNS["link"].search(message)
    if link:
        event, server_round, examples = link.group(1), int(link.group(2)), link.group(3)
        with _lock:
            entry = _rounds.setdefault(server_round, {})
            if event == "model_received":
                entry["model_at"] = now
            else:
                entry["aggregate_at"] = now
                entry["failed"] = event == "failed"
                if examples:
                    entry["examples"] = int(examples)


def reset() -> None:
    with _lock:
        _rounds.clear()


def session_cycles() -> list:
    """per round: round_s, from the server's test of the previous round to this one's (the whole
    round as this level lives it); work_s, for a lower level, from the upper model's arrival to its
    aggregate's departure (what the upper level waits for)"""
    with _lock:
        rounds = {number: dict(entry) for number, entry in _rounds.items()}
    cycles = []
    for number in sorted(n for n in rounds if n > 0):
        entry, previous = rounds[number], rounds.get(number - 1, {})
        cycle = {"round": number}
        if "test_at" in entry and "test_at" in previous:
            cycle["round_s"] = round(entry["test_at"] - previous["test_at"], 2)
        if "aggregate_at" in entry and "model_at" in entry:
            cycle["work_s"] = round(entry["aggregate_at"] - entry["model_at"], 2)
        if "examples" in entry:
            cycle["examples"] = entry["examples"]
        if entry.get("failed"):
            cycle["failed"] = True
        if len(cycle) > 1:
            cycles.append(cycle)
    return cycles
