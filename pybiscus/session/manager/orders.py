"""The manager's orders to its agents. The agents ask for them (GET /pybiscus-session/orders) and
post their results: the manager never calls an agent, which may sit behind a NAT or listen on its
loopback only."""

import hmac
import itertools
import threading
import time
from collections import deque
from typing import Optional

# the agent proves it is the one registered under its name with the call token it gave then: the
# session token is shared by every participant, who could otherwise take another agent's orders
CALL_TOKEN_HEADER = "X-Pybiscus-Call-Token"

# what an agent does on order; its answer is a dict, {"done": bool, ...}
STOP, STOP_AFTER_ROUND, RELAUNCH, LISTENING = "stop", "stop_after_round", "relaunch", "listening"
# to the server agent: a client's run configuration, kept in the server run's reports
CLIENT_RUNCONFIG = "client_runconfig"
KINDS = (STOP, STOP_AFTER_ROUND, RELAUNCH, LISTENING, CLIENT_RUNCONFIG)

# seconds between two questions of an agent: a stop or a relaunch waits at most this long
POLL_BUSY_S = 1.0
POLL_IDLE_S = 5.0
# an agent unheard of for longer has stopped, or lost its way to the manager
SEEN_WITHIN_S = 3 * POLL_IDLE_S
# what an agent is told to do must still make sense when it comes back (a stop after a restart)
ORDER_EXPIRY_S = 60.0

_lock = threading.Lock()
_ids = itertools.count(1)
_queued: dict = {}       # agent name -> deque of orders not yet taken
_taken: dict = {}        # order id -> order taken, its result awaited
last_seen: dict = {}     # agent name -> time of its last question


class Order:

    def __init__(self, agent: str, token: Optional[str], kind: str, args: dict):
        # the call token the agent registered with when the order was given: a drop clears the
        # registrations right after ordering the stops
        self.id, self.agent, self.token, self.kind, self.args = next(_ids), agent, token, kind, args
        self.created = time.monotonic()
        self.result: Optional[dict] = None
        self.done = threading.Event()

    def message(self) -> dict:
        return {"id": self.id, "kind": self.kind, "args": self.args}


def _same(offered: Optional[str], expected: Optional[str]) -> bool:
    return bool(offered and expected) and hmac.compare_digest(offered.encode(), expected.encode())


def send(agent: str, kind: str, **args) -> Order:
    import pybiscus.session.manager.session_manager as sm
    order = Order(agent, sm.agent_call_tokens.get(agent), kind, args)
    with _lock:
        _queued.setdefault(agent, deque()).append(order)
    return order


def withdraw(order: Order) -> bool:
    """an order its sender stopped waiting for, if not taken yet: a relaunch must not come late"""
    with _lock:
        queue = _queued.get(order.agent)
        if queue and order in queue:
            queue.remove(order)
            return True
    return False


def ask(agent: str, kind: str, timeout: float = POLL_IDLE_S + 5, **args) -> Optional[dict]:
    """the agent's answer, None when it did not take the order in time (the order is withdrawn) or
    did not answer"""
    order = send(agent, kind, **args)
    if order.done.wait(timeout):
        return order.result
    withdraw(order)
    return None


def heard(agent: str) -> None:
    last_seen[agent] = time.time()


def take(agent: str, token: Optional[str]) -> list:
    """the orders given to the agent registered under this name with this call token"""
    with _lock:
        heard(agent)
        now = time.monotonic()
        queue = deque(order for order in _queued.pop(agent, ()) if now - order.created < ORDER_EXPIRY_S)
        fresh = [order for order in queue if _same(token, order.token)]
        # another one presenting the name keeps nothing; the real agent takes them at its question
        rest = deque(order for order in queue if order not in fresh)
        if rest:
            _queued[agent] = rest
        # taken by an agent that ended before answering
        for order_id in [i for i, order in _taken.items() if now - order.created >= ORDER_EXPIRY_S]:
            del _taken[order_id]
        for order in fresh:
            _taken[order.id] = order
    return [order.message() for order in fresh]


def complete(agent: str, token: Optional[str], order_id: int, result: dict) -> bool:
    with _lock:
        order = _taken.get(order_id)
        if order is None or order.agent != agent or not _same(token, order.token):
            return False
        del _taken[order_id]
    order.result = result
    order.done.set()
    return True


def seen(agent: str) -> Optional[bool]:
    """None when the agent never asked"""
    when = last_seen.get(agent)
    return None if when is None else time.time() - when < SEEN_WITHIN_S
