import queue
import subprocess
import threading
from collections import deque

import click
from rich import print as rich_print

from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.session.agent import agent_weblog
from pybiscus.session.agent.agent_weblog import AgentState

# le buffer permet à la page de suivi de retrouver l'historique après un rechargement,
# et borne la mémoire d'un run long (des milliers de lignes par époque)
MAX_BUFFERED_LINES = 5000

IDLE    = "idle"
RUNNING = "running"
SUCCESS = "success"
FAILURE = "failure"


class RunSession:
    """Exécute pybiscus en tâche de fond et diffuse ses lignes de log aux pages de suivi."""

    def __init__(self):
        self._lock        = threading.Lock()
        self._lines       = deque(maxlen=MAX_BUFFERED_LINES)
        self._subscribers = set()
        self._process     = None

        self.mode   = None
        self.status = IDLE
        self.detail = ""

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

        self._publish({"type": "reset", "mode": mode})

        agent_weblog.agent_logger.log(f"launching pybiscus {mode}", state=AgentState.EXECUTING)

        threading.Thread(target=self._run, args=(command,), daemon=True).start()

    def stop(self) -> bool:
        process = self._process
        if process is None or process.poll() is not None:
            return False
        process.terminate()
        return True

    def _run(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._process = process

            invalid_config = False

            for line in process.stdout:
                rich_print(line, end="")

                line = click.unstyle(line).rstrip("\n")

                if "This is not a valid config!" in line:
                    invalid_config = True

                self._append_line(line)

            return_code = process.wait()

            if invalid_config:
                agent_weblog.agent_logger.log("Validation error !", state=AgentState.NOT_VALIDATED)
                self._set_status(FAILURE, "invalid configuration")
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
