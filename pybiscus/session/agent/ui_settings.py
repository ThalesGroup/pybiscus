import json
import os
from numbers import Real
from typing import Optional

import pybiscus.core.pybiscus_logger as logm

# Display settings of the agent's pages, on two levels: the machine's defaults, shared by the
# agents started there, and this agent's own values, which win. Agents of one machine usually
# run from the same directory: a single settings file would be shared by all of them, and a
# per-agent file needs a name that tells them apart, hence the agent's port.
SETTINGS_DIR = ".pybiscus-cache/ui-settings"

LIST_VIEWS = ("compact", "expanded")

# name -> (kind, default, constraints); served to the page, which builds its settings panel from it
SPEC = {
    "vertical_tabs_min_options":     ("int",    3,       {"min": 2, "max": 50}),
    "large_union_min_options":       ("int",    9,       {"min": 2, "max": 100}),
    "options_column_max_width_rem":  ("number", 16,      {"min": 6, "max": 40}),
    "options_column_max_height_rem": ("number", 22,      {"min": 8, "max": 80}),
    "field_name_column_width_rem":   ("number", 13,      {"min": 6, "max": 40}),
    # bold-stable: bold, with every option's width reserved for its bold label (no shift on selection)
    "active_option_weight":          ("choice", "bold-stable", {"choices": ["bold-stable", "bold", "semibold"]}),
    "large_union_mode":              ("choice", "chips", {"choices": ["chips", "radial", "column"]}),
    # list prefix -> view; a list absent from it shows compact
    "list_views":                    ("views",  {},      {"choices": list(LIST_VIEWS)}),
}

DEFAULTS = {name: default for name, (_, default, _) in SPEC.items()}

_agent_port: Optional[int] = None


def set_agent_port(port: int) -> None:
    global _agent_port
    _agent_port = port


def _path(scope: str) -> str:
    if scope == "machine":
        return os.path.join(SETTINGS_DIR, "machine.json")
    if scope == "agent" and _agent_port is not None:
        return os.path.join(SETTINGS_DIR, f"{_agent_port}.json")
    raise ValueError(f"unknown settings scope: {scope}")


def _read(scope: str) -> dict:
    try:
        with open(_path(scope), encoding="utf-8") as f:
            values = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logm.console.log(f"ui settings: {scope} file ignored, unreadable: {e}")
        return {}
    # a hand-edited file may hold anything: keep only what would be accepted from the page
    return {name: value for name, value in values.items() if name in SPEC and _valid(name, value)} if isinstance(values, dict) else {}


def _write(scope: str, values: dict) -> None:
    path = _path(scope)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # several agents of one machine may save at the same time: never leave a half-written file
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _valid(name: str, value) -> bool:
    kind, _, rules = SPEC[name]
    if kind in ("int", "number"):
        if isinstance(value, bool) or not isinstance(value, Real):
            return False
        if kind == "int" and value != int(value):
            return False
        return rules["min"] <= value <= rules["max"]
    if kind == "choice":
        return value in rules["choices"]
    if kind == "views":
        return isinstance(value, dict) and all(isinstance(k, str) and v in LIST_VIEWS for k, v in value.items())
    return False


def _merge(base: dict, overrides: dict) -> dict:
    merged = dict(base)
    for name, value in overrides.items():
        merged[name] = {**base.get(name, {}), **value} if SPEC[name][0] == "views" else value
    return merged


def state() -> dict:
    machine, agent = _read("machine"), _read("agent") if _agent_port is not None else {}
    return {
        "spec": {name: {"kind": kind, "default": default, **rules} for name, (kind, default, rules) in SPEC.items()},
        "agent_port": _agent_port,
        "machine": machine,
        "agent": agent,
        "effective": _merge(_merge(DEFAULTS, machine), agent),
    }


def update(scope: str, values: dict) -> dict:
    """values: name -> new value, or None to fall back to the level below; for list_views, a
    dict of list prefix -> view (None for one prefix, or None for the whole dict)"""

    if scope not in ("machine", "agent"):
        raise ValueError(f"unknown settings scope: {scope}")
    for name, value in values.items():
        if name not in SPEC:
            raise ValueError(f"unknown setting: {name}")
        if value is not None and SPEC[name][0] == "views":
            if not isinstance(value, dict) or not _valid(name, {k: v for k, v in value.items() if v is not None}):
                raise ValueError(f"invalid value for {name}: {value!r}")
        elif value is not None and not _valid(name, value):
            raise ValueError(f"invalid value for {name}: {value!r}")

    stored = _read(scope)
    below = DEFAULTS if scope == "machine" else _merge(DEFAULTS, _read("machine"))

    for name, value in values.items():
        if SPEC[name][0] == "views":
            views = {} if value is None else {**stored.get(name, {}), **value}
            # a view equal to what the level below gives is not an override
            views = {k: v for k, v in views.items() if v is not None and v != below[name].get(k, "compact")}
            if views:
                stored[name] = views
            else:
                stored.pop(name, None)
        elif value is None or value == below[name]:
            stored.pop(name, None)
        else:
            stored[name] = value

    _write(scope, stored)

    # saved for the whole machine: this agent's own values for the same settings would hide it
    if scope == "machine" and _agent_port is not None:
        agent = _read("agent")
        before = json.dumps(agent, sort_keys=True)
        for name, value in values.items():
            if SPEC[name][0] == "views" and value is not None and name in agent:
                agent[name] = {k: v for k, v in agent[name].items() if k not in value}
                if not agent[name]:
                    agent.pop(name)
            else:
                agent.pop(name, None)
        if json.dumps(agent, sort_keys=True) != before:
            _write("agent", agent)

    return state()


def reset(scope: str) -> dict:
    try:
        os.remove(_path(scope))
    except FileNotFoundError:
        pass
    return state()
