"""--record: the manager films its sessions with the recorder of the repository
(launch/doc/record_session.py shoot --attach), run by uv in a process of its own: Playwright and its
Chromium stay out of the manager's dependencies."""

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import pybiscus.core.pybiscus_logger as logm

RECORDER = Path(__file__).resolve().parents[3] / "launch" / "doc" / "record_session.py"
# a recorder ending this soon with an error could not start (browser, uv): starting it again would fail again
FAILED_START = 60


def missing_requirements() -> list:
    checks = (("uv", shutil.which("uv")), ("ffmpeg", shutil.which("ffmpeg")),
              (f"the recorder {RECORDER} (a checkout of the repository)", RECORDER.is_file()))
    return [what for what, found in checks if not found]


class Recording:
    """one recorder at a time; a new one starts when the manager is ready for a new session: no agent
    registered (at its start, after a drop), or a session launched while none was recording"""

    def __init__(self, directory: Path, manager_url: str, name: str, admin_token: Optional[str],
                 no_agent: Callable[[], bool], poll: float = 2.0):
        self.directory, self.manager_url, self.name = directory.resolve(), manager_url, name
        self.admin_token, self.no_agent, self.poll = admin_token, no_agent, poll
        self.proc, self.rushes, self.started = None, None, 0.0
        self.launched_unrecorded = False
        self.stopping = threading.Event()
        self.lock = threading.Lock()

    def start(self) -> None:
        # the first recorder waits for a poll: the manager must answer when it attaches
        self.directory.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._loop, name="recording", daemon=True).start()

    def recording(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def session_launched(self) -> None:
        if not self.recording():
            self.launched_unrecorded = True

    def _loop(self) -> None:
        while not self.stopping.wait(self.poll):
            with self.lock:
                if self.recording() or self.stopping.is_set():
                    continue
                if self.proc is not None:
                    started = self._ended()
                    self.proc = None
                    if not started:
                        return
                if self.no_agent() or self.launched_unrecorded:
                    self._launch()

    def _launch(self) -> None:
        self.launched_unrecorded = False
        self.rushes = self.directory / f"rushes-{self.name}-{time.strftime('%Y%m%d-%H%M%S')}"
        log = open(self.rushes.with_name(self.rushes.name + ".log"), "w")
        # the recorder has its own environment (its script's dependencies), not the manager's
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYBISCUS_MANAGER_TOKEN")}
        if self.admin_token:
            env["PYBISCUS_MANAGER_TOKEN"] = self.admin_token
        # its own process group: the manager's Ctrl+C must not end the browser before the rushes are edited
        self.proc = subprocess.Popen(["uv", "run", "--quiet", str(RECORDER), "shoot", "--attach", self.manager_url,
                                      "--rushes", str(self.rushes)],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env,
                                     start_new_session=True)
        log.close()
        self.started = time.monotonic()
        logm.console.log(f"🎥 recording the session into {self.rushes}")

    def _ended(self) -> bool:
        """False: the recorder could not start, recording stops"""
        code, log = self.proc.returncode, self.rushes.with_name(self.rushes.name + ".log")
        video = self.rushes / "video.mp4"
        if code == 0:
            logm.console.log(f"🎬 session recorded: {video if video.exists() else self.rushes}")
            return True
        if time.monotonic() - self.started < FAILED_START:
            logm.console.log(f"⚠️ the recorder could not start (exit {code}), recording stops: see {log}")
            return False
        logm.console.log(f"⚠️ the recorder ended with an error (exit {code}): see {log}")
        return True

    def stop(self) -> None:
        """the manager stops: the recorder ends its shooting and edits it, on its own"""
        self.stopping.set()
        with self.lock:
            if self.recording():
                os.killpg(self.proc.pid, signal.SIGINT)
                logm.console.log(f"🎬 the recording ends; its video is being edited into {self.rushes / 'video.mp4'}")
