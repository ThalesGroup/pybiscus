"""The agent asks its manager for orders (stop, relaunch...) and posts their results: the manager
never calls the agent, which may sit behind a NAT or listen on its loopback only."""

import re
import socket
import threading
import time
from typing import Optional

import requests

from pybiscus.session.agent.run_session import run_session
from pybiscus.session.auth import headers_for
from pybiscus.session.manager.orders import (CALL_TOKEN_HEADER, CLIENT_RUNCONFIG, LISTENING, POLL_IDLE_S, RELAUNCH,
                                             STOP, STOP_AFTER_ROUND)

_lock = threading.Lock()
_target: Optional[dict] = None   # {"manager_url", "name", "call_token"}
_thread: Optional[threading.Thread] = None


def follow(manager_url: str, name: str, call_token: str) -> None:
    """asks this manager under this name from now on (at the start with --config, at each
    registration)"""
    global _target, _thread
    with _lock:
        _target = {"manager_url": manager_url.rstrip("/"), "name": name, "call_token": call_token}
        if _thread is None:
            _thread = threading.Thread(target=_loop, name="manager-orders", daemon=True)
            _thread.start()


def _loop() -> None:
    session = requests.Session()
    unreachable_since = None
    while True:
        with _lock:
            target = dict(_target)
        pause = POLL_IDLE_S
        try:
            pause = _ask(session, target)
            if unreachable_since is not None:
                print(f"✅ the manager {target['manager_url']} answers again", flush=True)
            unreachable_since = None
        except (requests.RequestException, ValueError) as error:
            # said once: the agent asks again every few seconds
            if unreachable_since is None:
                unreachable_since = time.time()
                print(f"⚠️ the manager {target['manager_url']} does not answer the agent's questions ({type(error).__name__}); "
                      "asking again", flush=True)
        time.sleep(pause)


def _ask(session: requests.Session, target: dict) -> float:
    url = f"{target['manager_url']}/pybiscus-session/orders"
    headers = {**headers_for(url), CALL_TOKEN_HEADER: target["call_token"]}
    response = session.get(url, params={"agent": target["name"]}, headers=headers, timeout=10)
    if response.status_code != 200:
        # refused (invitation revoked, name taken): no orders, the agent asks again later
        return POLL_IDLE_S
    answer = response.json()
    for order in answer.get("orders", []):
        result = execute(order.get("kind"), order.get("args") or {})
        session.post(f"{url}/{order['id']}", params={"agent": target["name"]}, json=result, headers=headers, timeout=10)
    pace = answer.get("next")
    return pace if isinstance(pace, (int, float)) and 0.2 <= pace <= 60 else POLL_IDLE_S


def execute(kind: str, args: dict) -> dict:
    if kind == STOP:
        return {"done": True} if run_session.stop() else {"done": False, "reason": "no running process"}
    if kind == STOP_AFTER_ROUND:
        return ({"done": True} if run_session.stop_after_round()
                else {"done": False, "reason": "no running server process"})
    if kind == RELAUNCH:
        return ({"done": True, "mode": run_session.mode} if run_session.relaunch()
                else {"done": False, "reason": "no run to launch again, or still running"})
    if kind == LISTENING:
        return server_listening(args.get("port"))
    if kind == CLIENT_RUNCONFIG:
        return keep_client_runconfig(args.get("client"), args.get("yaml"))
    return {"done": False, "reason": f"unknown order {kind!r}"}


def server_listening(asked) -> dict:
    """whether this agent's server run listens: probed here, on the server's machine, since the
    manager may not reach a server listening on the loopback only. Only the port of this agent's
    server run is probed: any port asked for would tell which services listen on this machine"""
    port = run_session.server_port()
    if port is None:
        return {"done": False, "reason": "no server run whose port is known"}
    if asked is not None and str(asked) != str(port):
        return {"done": False, "reason": f"only the port of this agent's server run is probed ({port})"}
    listening = False
    # localhost may resolve to IPv4 only, and the session form listens on [::1] or [::]
    for loopback in ("::1", "127.0.0.1"):
        try:
            socket.create_connection((loopback, port), timeout=1).close()
            listening = True
            break
        except OSError:
            pass
    return {"done": True, "listening": listening, "running": run_session.is_running()}


def keep_client_runconfig(client, text) -> dict:
    """kept where the server run takes it into its reports at its end"""
    import pybiscus.session.agent.pybiscus_agent as pybagent
    from pybiscus.commands.apps_common import client_configs_dir
    if pybagent.registration_parameters.get("role") != "server":
        return {"done": False, "reason": "not a server agent"}
    # the file's name: a name with a path would write elsewhere
    if not isinstance(client, str) or not re.fullmatch(r"[\w.-]{1,100}", client) or client.startswith("."):
        return {"done": False, "reason": f"not a client name: {client!r}"}
    if not isinstance(text, str):
        return {"done": False, "reason": "no configuration"}
    path = client_configs_dir() / f"{client}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"done": True}
