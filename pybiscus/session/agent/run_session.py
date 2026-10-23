import os
import queue
import re
import subprocess
import threading
from collections import deque

import click
from rich import print as rich_print

from pybiscus.commands.apps_common import CONFIG_VALIDATION_EXIT_CODE
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.core.stop_signal import STOP_SIGNAL
from pybiscus.session.agent import agent_weblog
from pybiscus.session.agent.agent_weblog import AgentState

# le buffer permet à la page de suivi de retrouver l'historique après un rechargement,
# et borne la mémoire d'un run long (des milliers de lignes par époque)
MAX_BUFFERED_LINES = 5000

# Rich gives a process without a terminal 80 columns: a line of gui_events.py was cut in two, and the
# monitor's patterns missed it. Wider, Rich pushes the source file to the end of the line: the padding
# is brought back to two spaces
RUN_CONSOLE_COLUMNS = "200"
LOG_PATH_PADDING = re.compile(r"\s{3,}(\S+\.py:\d+)\s*$")

IDLE    = "idle"
RUNNING = "running"
SUCCESS = "success"
FAILURE = "failure"
STOPPED = "stopped"


class RunSession:
    """Exécute pybiscus en tâche de fond et diffuse ses lignes de log aux pages de suivi."""

    def __init__(self):
        self._lock        = threading.Lock()
        self._lines       = deque(maxlen=MAX_BUFFERED_LINES)
        self._subscribers = set()
        self._process     = None
        # the terminated process exits with a non-zero code: without this, a stop looked like a failure
        self._stop_requested = False
        # a server stopped after its round exits with 0, as at its last round
        self._stop_after_round_requested = False

        self.mode   = None
        self.status = IDLE
        self.detail = ""
        # the last run launched, which the manager has run again at the deadlines of a repeated session
        self._command = None

    # ---------- lecture ----------

    def snapshot(self):
        with self._lock:
            return {
                "mode":   self.mode,
                "status": self.status,
                "detail": self.detail,
                "lines":  list(self._lines),
            }

    def is_running(self) -> bool:
        with self._lock:
            return self.status == RUNNING

    def server_port(self) -> int | None:
        """the port the last server run listens on, read from its configuration: None if the last
        run was not a server's, or its address cannot be read"""
        with self._lock:
            mode, command = self.mode, self._command
        if mode != "server" or not command:
            return None
        from omegaconf import OmegaConf
        from pybiscus.flower_config.config_server import ConfigFlowerServer
        try:
            listen = OmegaConf.select(OmegaConf.load(command[-1]), "flower_server.listen_address", default=None)
        except Exception:
            return None
        listen = listen or ConfigFlowerServer.model_fields["listen_address"].default
        try:
            return int(str(listen).rpartition(":")[2])
        except ValueError:
            return None

    # ---------- diffusion ----------

    def subscribe(self) -> queue.Queue:
        subscriber = queue.Queue()
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def _publish(self, event: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(event)

    def _append_line(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
        self._publish({"type": "log", "line": line})

    def _set_status(self, status: str, detail: str = "") -> None:
        with self._lock:
            self.status = status
            self.detail = detail
        self._publish({"type": "status", "status": status, "detail": detail})

    # ---------- exécution ----------

    def start(self, mode: str, command: list[str]) -> None:
        with self._lock:
            if self.status == RUNNING:
                raise PybiscusValueException("a run is already in progress")
            self._lines.clear()
            self.mode   = mode
            self.status = RUNNING
            self.detail = ""
            self._stop_requested = False
            self._stop_after_round_requested = False
            self._command = command

        self._publish({"type": "reset", "mode": mode})

        agent_weblog.agent_logger.log(f"launching pybiscus {mode}", state=AgentState.EXECUTING)

        threading.Thread(target=self._run, args=(command,), daemon=True).start()

    def relaunch(self) -> bool:
        """the last run again, with the configuration it was launched with: False if none was, or if
        it still runs"""
        with self._lock:
            mode, command, running = self.mode, self._command, self.status == RUNNING
        if command is None or running:
            return False
        self.start(mode, command)
        return True

    def stop(self) -> bool:
        process = self._process
        if process is None or process.poll() is not None:
            return False
        self._stop_requested = True
        process.terminate()
        return True

    def stop_after_round(self) -> bool:
        process = self._process
        if STOP_SIGNAL is None or self.mode != "server" or process is None or process.poll() is not None:
            return False
        self._stop_after_round_requested = True
        # uv run forwards it to the pybiscus process it started
        process.send_signal(STOP_SIGNAL)
        return True

    def _run(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "COLUMNS": RUN_CONSOLE_COLUMNS},
            )
            self._process = process

            for line in process.stdout:
                line = LOG_PATH_PADDING.sub(r"  \1", click.unstyle(line).rstrip("\n"))

                rich_print(line)

                self._append_line(line)

            return_code = process.wait()

            if return_code == CONFIG_VALIDATION_EXIT_CODE:
                agent_weblog.agent_logger.log("Validation error !", state=AgentState.NOT_VALIDATED)
                self._set_status(FAILURE, "invalid configuration")
            elif self._stop_requested:
                agent_weblog.agent_logger.log("pybiscus run stopped by the operator", state=AgentState.STOPPED)
                self._set_status(STOPPED, "stopped by the operator")
            elif return_code == 0 and self._stop_after_round_requested:
                agent_weblog.agent_logger.log("pybiscus run stopped after its round by the operator", state=AgentState.STOPPED)
                self._set_status(STOPPED, "stopped after its round by the operator")
            elif return_code == 0:
                agent_weblog.agent_logger.log("pybiscus run completed", state=AgentState.TERMINATED)
                self._set_status(SUCCESS, "pybiscus run completed")
            else:
                agent_weblog.agent_logger.log(
                    f"Processus {command} has failed with code {return_code}",
                    state=AgentState.FAILED,
                )
                self._set_status(FAILURE, f"process failed with code {return_code}")

        except Exception as e:
            self._append_line(f"[agent] {e}")
            agent_weblog.agent_logger.log(f"pybiscus run failed : {e}", state=AgentState.FAILED)
            self._set_status(FAILURE, str(e))


run_session = RunSession()
