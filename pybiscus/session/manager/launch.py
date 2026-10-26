"""The runs of the agents started with --accept-launch, launched by order when the session is (the
others are launched from their configuration form, by their operator): the servers first, the
clients once every server listens, since Flower's legacy client does not retry."""

import threading
import time
from typing import Optional

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.session.manager import orders
from pybiscus.session.manager.network import flower_server_address

POLL_S = 1.0
# loading the plugins and the model before listening: tens of seconds on a loaded machine
SERVER_START_LIMIT_S = 600
# a server its operator launches from the form: the clients launched by order wait for it this long
OPERATOR_LIMIT_S = 1800


def accepts(name: str) -> bool:
    return bool(sm.registered_agents_meta.get(name, {}).get("accept_launch"))


def wait_listening(name: str, limit: float, cancelled: threading.Event, patient: bool = False) -> Optional[str]:
    """None once the server of this agent listens, else why it does not; patient: its run is not
    configured yet (its operator launches it), which is no failure"""
    port, _ = flower_server_address()
    if port is None:
        return f"the port of {name}'s Flower server is unknown: its clients cannot wait for it"
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        state = orders.ask(name, orders.LISTENING, port=port)
        if state is None and not patient:
            return f"{name} did not answer while its server starts"
        if state is not None and state.get("listening"):
            return None
        if state is not None and not patient:
            if "listening" not in state:
                return f"{name} did not probe its server's port {port} ({state.get('reason', '')})"
            if not state.get("running"):
                return f"the Flower server of agent {name} ended before listening"
        if cancelled.wait(POLL_S):
            return "cancelled"
    return f"the Flower server of agent {name} did not listen within {limit} s"


def launch_one(name: str) -> Optional[str]:
    answer = orders.ask(name, orders.LAUNCH, answer_within=orders.SLOW_ANSWER_S)
    if answer is None:
        return f"{name} did not take the order to launch its run (stopped, or cut from the manager), or did not answer"
    if not answer.get("done"):
        return f"{name} did not launch its run: {answer.get('reason', '')}"
    logm.console.log(f"🚀 {name}: run launched by order")
    return None


_cancelled = threading.Event()


def _report(problem: Optional[str]) -> None:
    if problem:
        logm.console.log(f"⚠️ {problem}")


def _clients_once_servers_listen(clients: list) -> None:
    for server in list(sm.registered_servers):
        launched_by_order = accepts(server)
        problem = wait_listening(server, SERVER_START_LIMIT_S if launched_by_order else OPERATOR_LIMIT_S, _cancelled,
                                 patient=not launched_by_order)
        if problem == "cancelled":
            return
        if problem:
            return _report(f"{', '.join(clients)} not launched by order: {problem}")
    for name in clients:
        _report(launch_one(name))


def _launch(clients: list) -> None:
    for name in list(sm.registered_servers):
        if accepts(name):
            _report(launch_one(name))
    if clients:
        _clients_once_servers_listen(clients)


def session_launched() -> None:
    """the session's agents that accept it launched by order, in a thread: the session form's request
    answers at once"""
    _cancelled.clear()
    clients = [name for name in [*sm.session_clients, *sm.session_relays] if accepts(name)]
    if clients or any(accepts(name) for name in sm.registered_servers):
        threading.Thread(target=_launch, args=(clients,), name="launch-by-order", daemon=True).start()


def registered_late(name: str) -> None:
    """an agent accepting it, registered once the session runs: launched as the others were"""
    if not (sm.session_is_running and accepts(name)):
        return
    target, args = (_report_launch, (name,)) if name in sm.registered_servers else (_clients_once_servers_listen, ([name],))
    threading.Thread(target=target, args=args, name="launch-by-order", daemon=True).start()


def _report_launch(name: str) -> None:
    _report(launch_one(name))


def cancel() -> None:
    """a dropped session: the clients waiting for their server are not launched"""
    _cancelled.set()
