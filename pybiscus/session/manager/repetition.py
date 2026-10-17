import threading
import time
from typing import Optional

import requests

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.core.schedule import ConfigSchedule, Schedule
from pybiscus.session.agent.agent_weblog import AgentState
from pybiscus.session.csrf import HEADER
from pybiscus.session.manager.network import flower_server_address

# A session launched again at each deadline (variant B of the rounds at fixed times): the operator
# checks and launches the first one as any other; when all its runs have ended, the manager waits
# for the next deadline and has each agent run its last configuration again, the server first. The
# server starts from the final weights of the previous session (server_run.weights_path: latest),
# the clients read their data again at their start, an incremental module only what is new.

RUNNING, WAITING, ENDED, FAILED = "running", "waiting", "ended", "failed"
POLL_S = 1.0
# loading the plugins and the model before listening: tens of seconds on a loaded machine
SERVER_START_LIMIT_S = 600


class Repetition:

    def __init__(self, config: ConfigSchedule):
        self.config = config
        self.schedule = Schedule(config)
        # the operator's launch is the first deadline: the next ones follow it, whatever `start` says
        self.schedule.previous = self.schedule.now()
        self.sessions = 1
        self.status = RUNNING
        self.reason: Optional[str] = None
        self.next_deadline = None
        self.stop_requested = False
        self.cancelled = threading.Event()
        # those of an earlier session left in place: all final, they would launch the next one at once
        for name in self._participants():
            sm.agent_states.pop(name, None)
        threading.Thread(target=self._loop, daemon=True).start()

    def state(self) -> dict:
        return {"status": self.status, "sessions": self.sessions, "reason": self.reason,
                "stop_requested": self.stop_requested,
                "next_deadline": self.next_deadline.isoformat(timespec="seconds") if self.next_deadline else None,
                "schedule": self.config.every or self.config.cron}

    def request_stop(self) -> None:
        """no session after the current one; the current one goes on"""
        self.stop_requested = True
        logm.console.log("🔁 repetition: no session after the current one")

    def cancel(self) -> None:
        self.cancelled.set()

    def _participants(self) -> dict:
        return {name: url for name, url in {**sm.registered_servers, **sm.registered_clients}.items()
                if name in sm.registered_servers or name in sm.session_clients or name in sm.session_relays}

    def _end(self, status: str, reason: str) -> None:
        self.status, self.reason, self.next_deadline = status, reason, None
        logm.console.log(f"🔁 repetition {status} after {self.sessions} session(s): {reason}")

    def _wait_for_runs(self) -> Optional[dict]:
        """the final states of the session's runs, None when the repetition is cancelled"""
        while not self.cancelled.wait(POLL_S):
            participants = self._participants()
            states = {name: sm.agent_states.get(name) for name in participants}
            if participants and all(state in AgentState.FINAL for state in states.values()):
                return states
        return None

    def _loop(self) -> None:
        while True:
            states = self._wait_for_runs()
            if states is None:
                return
            failed = sorted(name for name, state in states.items() if state == AgentState.FAILED)
            if failed:
                # a defect would come back at each deadline unnoticed: the operator looks first
                return self._end(FAILED, f"the run of {', '.join(failed)} failed in session {self.sessions}")
            if self.stop_requested:
                return self._end(ENDED, "stopped by the operator")
            self.next_deadline = self.schedule.next_deadline()
            self.status = WAITING
            logm.console.log(f"🔁 session {self.sessions + 1} at {self.next_deadline.isoformat(sep=' ', timespec='seconds')}")
            while (remaining := (self.next_deadline - self.schedule.now()).total_seconds()) > 0:
                if self.cancelled.wait(min(remaining, POLL_S)):
                    return
                if self.stop_requested:
                    return self._end(ENDED, "stopped by the operator")
            problem = self._relaunch()
            if self.cancelled.is_set():
                return
            if problem:
                return self._end(FAILED, problem)

    def _relaunch(self) -> Optional[str]:
        participants = self._participants()
        # read again before they report: the previous session's final states would end this one at once
        for name in participants:
            sm.agent_states.pop(name, None)
        self.sessions += 1
        self.status, self.next_deadline = RUNNING, None
        headers = {HEADER: "1", "Authorization": f"Bearer {sm.session_token}"}
        servers = [name for name in participants if name in sm.registered_servers]
        for name in servers:
            if problem := self._relaunch_one(name, participants[name], headers):
                return problem
        # Flower's legacy client does not retry: started before its server listens, it fails at once
        for name in servers:
            if problem := self._wait_listening(name, participants[name], headers):
                return problem
        for name in participants:
            if name not in sm.registered_servers and (problem := self._relaunch_one(name, participants[name], headers)):
                return problem
        logm.console.log(f"🔁 session {self.sessions} launched")
        return None

    def _relaunch_one(self, name: str, url: str, headers: dict) -> Optional[str]:
        try:
            response = requests.post(f"{url.rstrip('/')}/run/relaunch", headers=headers, timeout=10)
        except requests.RequestException as error:
            return f"{name} could not be reached to launch session {self.sessions} ({type(error).__name__})"
        if response.status_code != 202:
            return f"{name} did not launch session {self.sessions} (HTTP {response.status_code}: {response.text.strip()})"
        return None

    def _wait_listening(self, name: str, url: str, headers: dict) -> Optional[str]:
        port, _ = flower_server_address()
        if port is None:
            return f"the port of {name}'s Flower server is unknown: its clients cannot wait for it"
        deadline = time.monotonic() + SERVER_START_LIMIT_S
        while time.monotonic() < deadline:
            try:
                state = requests.get(f"{url.rstrip('/')}/run/listening", params={"port": port}, headers=headers, timeout=10).json()
            except (requests.RequestException, ValueError) as error:
                return f"{name} could not be reached while its server starts ({type(error).__name__})"
            if state.get("listening"):
                return None
            if not state.get("running"):
                return f"the Flower server of agent {name} ended before listening, in session {self.sessions}"
            if self.cancelled.wait(POLL_S):
                return "cancelled"
        return f"the Flower server of agent {name} did not listen within {SERVER_START_LIMIT_S} s, in session {self.sessions}"


repetition: Optional[Repetition] = None


def start(config: ConfigSchedule) -> None:
    global repetition
    cancel()
    repetition = Repetition(config)
    logm.console.log(f"🔁 the session is launched again at each deadline ({config.every or config.cron}, {repetition.schedule.zone})")


def cancel() -> None:
    global repetition
    if repetition is not None:
        repetition.cancel()
    repetition = None


def state() -> Optional[dict]:
    return repetition.state() if repetition is not None else None
