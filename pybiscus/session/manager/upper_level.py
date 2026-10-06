import json
import os
import threading
import time

import requests

import pybiscus.session.manager.session_manager as sm
from pybiscus.session.auth import local_manager_session_token
from pybiscus.session.csrf import HEADER

UPPER_TOKEN_ENV = "PYBISCUS_UPPER_TOKEN"
# the topology is compared locally this often, and sent only when it has changed
CHECK_PERIOD_S = 2
# without a change, only a heartbeat (the bouquet's name) tells the upper level this one is alive
HEARTBEAT_PERIOD_S = 10
STALE_AFTER_S = 3 * HEARTBEAT_PERIOD_S


def bouquet_topology() -> dict:
    """what this manager tells the upper level: its bouquet, its agents and, recursively, the
    lower levels reporting to it"""

    agents = [{"name": name, "role": role, "state": sm.agent_states.get(name, "declared"),
               **{key: value for key, value in sm.registered_agents_meta.get(name, {}).items() if key != "role"}}
              for role, registered in (("server", sm.registered_servers), ("client", sm.registered_clients))
              for name in registered]
    return {"bouquet": sm.bouquet, "color": sm.bouquet_color, "manager_url": sm.manager_url,
            "manager": manager_place(), "agents": agents, "lower_levels": lower_levels()}


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
                     "problem": None, "last_contact": None}

    def note_contact(response, problem):
        if problem is None:
            answer = response.json()
            sm.upper_link.update(bouquet=answer.get("bouquet"), color=answer.get("color"), reached=True,
                                 problem=None, last_contact=time.time())
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
            elif time.time() - last_contact >= HEARTBEAT_PERIOD_S:
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
