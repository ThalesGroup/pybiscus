import json
import os
import re
import threading
import time

import requests

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.flower.sessionlink import ConfigSessionLink
from pybiscus.session.auth import local_manager_session_token
from pybiscus.session.csrf import HEADER

UPPER_TOKEN_ENV = "PYBISCUS_UPPER_TOKEN"
# the topology is compared locally this often, and sent only when it has changed
CHECK_PERIOD_S = 2
# without a change, only a heartbeat (the bouquet's name) tells the upper level this one is alive
HEARTBEAT_PERIOD_S = 10
STALE_AFTER_S = 3 * HEARTBEAT_PERIOD_S
# the choices a lower level's session must keep: model (its hyperparameters too) and data, so that
# models of every level can be exchanged, and the number of rounds, each lower round answering one
# upper round
CONSTRAINED = ("model", "model_values", "data", "num_rounds")
# a setting of the manager's, not an option selected in every form
NOT_AN_OPTION = ("num_rounds",)
MODEL_VALUES = "model.config."
# the relay plugin's PYBISCUS_ALIAS, the tab its preset selects: the manager loads no plugin
RELAY_OPTION = "Relay"
RELAY_LINK = "flower_client.alternate_client_class.config"
SERVER_LINK = "server_strategy.upper_level_link"


def bouquet_topology() -> dict:
    """what this manager tells the upper level: its bouquet, its agents and, recursively, the
    lower levels reporting to it"""

    agents = [{"name": name, "role": role, "state": sm.agent_states.get(name, "declared"),
               **{key: value for key, value in sm.registered_agents_meta.get(name, {}).items() if key != "role"}}
              for role, registered in (("server", sm.registered_servers), ("client", sm.registered_clients))
              for name in registered]
    from pybiscus.session.manager.cycles import session_cycles
    return {"bouquet": sm.bouquet, "color": sm.bouquet_color, "manager_url": sm.manager_url,
            "manager": manager_place(), "agents": agents, "relays": dict(sm.relays), "lower_levels": lower_levels(),
            "cycles": session_cycles(), "session": session_state()}


def session_state() -> dict:
    """this session as an upper level checks it: what it applies and the link it was launched
    with, against what its parent imposes; the links it made for its own lower levels"""
    return {"running": sm.session_is_running, "constraints": sm.session_constraints,
            "link_id": (sm.upper_session_link or {}).get("link_id"),
            "links": {lower: link["link_id"] for lower, link in sm.session_links.items()},
            "dropped": (sm.upper_link or {}).get("dropped")}


def manager_place() -> dict:
    return {"location": sm.manager_location, "geo_location": sm.manager_geo}


def lower_levels() -> list:
    now = time.time()
    with sm.lower_levels_lock:
        reports = list(sm.lower_levels.values())
    return [{**report["topology"], "stale": now - report["last_seen"] > STALE_AFTER_S} for report in reports]


def upper_level():
    """the link to the upper-level manager as the page shows it, None without --upper-url"""
    if sm.upper_link is None:
        return None
    link = dict(sm.upper_link)
    link["since"] = None if link["last_contact"] is None else round(time.time() - link["last_contact"])
    return link


def session_for_lower_levels(bouquet: str) -> dict:
    """the session the lower levels must follow, and the client relaying this one, sent in every
    answer to them"""
    running = sm.session_is_running
    return {"running": running, "constraints": sm.session_constraints if running else None,
            "relay": sm.relays.get(bouquet), "link": sm.session_links.get(bouquet) if running else None}


def links_for_lower_levels() -> dict:
    """one link per lower level, new at each launch: a link_id used again would hand a lower level
    the files of an earlier run"""
    stamp = time.strftime("%Y%m%dT%H%M%S")
    return {lower: {**ConfigSessionLink().model_dump(),
                    "link_id": re.sub(r"[^A-Za-z0-9._-]", "_", f"{sm.bouquet or 'upper'}-{lower}-{stamp}")}
            for lower in sm.relays}


def link_presets(presets: dict, prefix: str, link: dict) -> None:
    for name, value in link.items():
        presets["values_set"][f"{prefix}.{name}"] = value
        presets["values_lock"].append(f"{prefix}.{name}")


def upper_level_session_link():
    """the link the upper level's running session made for this level, None before"""
    session = (sm.upper_link or {}).get("session") or {}
    return session.get("link") if session.get("running") else None


def follow_upper_session() -> None:
    """a lower level's session ends with the upper level's, or when the upper level launched
    another one (a new link this session's server would never read). An upper level out of reach
    changes nothing: it may come back"""
    if not sm.session_is_running or sm.upper_session_link is None:
        return
    current = upper_level_session_link()
    if current is not None and current.get("link_id") == sm.upper_session_link.get("link_id"):
        return
    from pybiscus.session.manager.routes.pybiscussession import drop_session
    reason = "launched another session" if current else "dropped its session"
    logm.console.log(f"🛑 the upper level {reason}: this session is dropped, its runs stopped")
    drop_session()
    sm.upper_link["dropped"] = f"the upper level {reason} at {time.strftime('%H:%M:%S')}: launch this session again"


def missing_relays() -> list:
    """the lower levels without a relay, or with a relay no longer registered"""
    with sm.lower_levels_lock:
        bouquets = list(sm.lower_levels)
    return [b for b in bouquets if sm.relays.get(b) not in sm.registered_clients]


def designate_relay(bouquet: str, client) -> None:
    """a client relays at most one lower level: designated for another, it leaves the first"""
    for other, relay in list(sm.relays.items()):
        if relay == client or other == bouquet:
            del sm.relays[other]
    if client:
        sm.relays[bouquet] = client


def upper_constraints():
    """the upper level's model and data once its session runs; None while it is not configured"""
    session = (sm.upper_link or {}).get("session") or {}
    return session.get("constraints") if session.get("running") else None


def apply_upper_constraints(presets: dict) -> None:
    """set and lock the upper level's choices, whatever the session form sent"""
    options_set = presets.setdefault("options_set", {})
    options_lock = presets.setdefault("options_lock", [])
    values_set = presets.setdefault("values_set", {})
    values_lock = presets.setdefault("values_lock", [])
    for key, value in upper_constraints().items():
        if key == "model_values":
            values_set.update(value)
            values_lock.extend(path for path in value if path not in values_lock)
            continue
        if key in NOT_AN_OPTION:
            presets[key] = value
            continue
        options_set[key] = value
        if key not in options_lock:
            options_lock.append(key)


def record_session_constraints(presets: dict) -> None:
    presets = presets or {}
    chosen = {**presets.get("options_set", {}), **{key: presets.get(key) for key in NOT_AN_OPTION},
              "model_values": {path: value for path, value in presets.get("values_set", {}).items() if path.startswith(MODEL_VALUES)}}
    sm.session_constraints = {key: chosen[key] for key in CONSTRAINED if chosen.get(key)} or None


def record_lower_level(topology: dict) -> None:
    with sm.lower_levels_lock:
        sm.lower_levels[topology["bouquet"]] = {"topology": topology, "last_seen": time.time()}


def lower_level_alive(bouquet: str) -> bool:
    """False for a bouquet this manager has no topology of (restarted since): the lower level then
    sends it again"""
    with sm.lower_levels_lock:
        report = sm.lower_levels.get(bouquet)
        if report is None:
            return False
        report["last_seen"] = time.time()
        return True


def _headers(url: str, token) -> dict:
    headers = {HEADER: "1"}
    # not headers_for(): its first choice, $PYBISCUS_SESSION_TOKEN, is this manager's own token
    token = token or os.environ.get(UPPER_TOKEN_ENV) or local_manager_session_token(url)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def report_to_upper_level(upper_url: str, token) -> None:
    """pushed rather than polled by the upper level, which does not know its lower levels'
    addresses"""

    base = upper_url.rstrip("/") + "/pybiscus-session/lower-level"
    sm.upper_link = {"url": upper_url.rstrip("/"), "bouquet": None, "color": None, "reached": None,
                     "problem": None, "last_contact": None, "session": None, "dropped": None}

    def note_contact(response, problem):
        if problem is None:
            answer = response.json()
            sm.upper_link.update(bouquet=answer.get("bouquet"), color=answer.get("color"), reached=True,
                                 problem=None, last_contact=time.time(), session=answer.get("session"))
            follow_upper_session()
        else:
            sm.upper_link.update(reached=False, problem=problem)

    def post(endpoint, payload):
        try:
            response = requests.post(endpoint, json=payload, headers=_headers(upper_url, token), timeout=5)
            return response, None if response.ok else f"HTTP {response.status_code}"
        except requests.RequestException as e:
            return None, type(e).__name__

    def loop():
        sent, last_contact, reached = None, 0.0, None
        while True:
            topology = json.dumps(bouquet_topology(), sort_keys=True)
            problem = None
            if topology != sent:
                response, problem = post(base, json.loads(topology))
                note_contact(response, problem)
                if problem is None:
                    sent, last_contact = topology, time.time()
            # while waiting for the upper level's session, often: its configuration unlocks this one's
            elif time.time() - last_contact >= (CHECK_PERIOD_S if upper_constraints() is None else HEARTBEAT_PERIOD_S):
                response, problem = post(base + "/heartbeat", {"bouquet": sm.bouquet})
                note_contact(response, problem)
                if problem is None:
                    last_contact = time.time()
                    if not response.json().get("known", False):
                        sent = None   # the upper level restarted: the whole topology at the next check
            now_reached = problem is None
            # once per change, not every few seconds
            if now_reached != reached:
                print(f"✅ reporting to the upper-level manager {upper_url}" if now_reached
                      else f"⚠️ upper-level manager {upper_url} not reached ({problem}), retrying", flush=True)
                reached = now_reached
            time.sleep(CHECK_PERIOD_S)

    threading.Thread(target=loop, name="upper-level-report", daemon=True).start()
