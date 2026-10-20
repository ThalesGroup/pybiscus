"""Recording of the manager's sessions (--record, or the session form's record): the recorder of the
repository (launch/doc/record_session.py shoot --attach), run by uv in a process of its own:
Playwright and its Chromium stay out of the manager's dependencies."""

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
DEFAULT_DIRECTORY = "experiments/recordings"
# a recorder ending this soon with an error could not start (browser, uv): starting it again would fail again
FAILED_START = 60
# the recorder's line once its shooting is over, before it edits the video
SHOT_LINE = "rushes in "
VIDEOS = ("video.mp4", "video.webp")


_missing = None


def missing_requirements() -> list:
    # checked once: the manager's page asks at every poll, and the tools do not come and go during a run
    global _missing
    if _missing is None:
        checks = (("uv", shutil.which("uv")), ("ffmpeg", shutil.which("ffmpeg")),
                  (f"the recorder {RECORDER} (a checkout of the repository)", RECORDER.is_file()))
        _missing = [what for what, found in checks if not found]
    return _missing


class Recording:
    """one recorder at a time. automatic (--record): a new one starts when the manager is ready for a
    new session, no agent registered (at its start, after a drop), or when a session is launched while
    none records; otherwise (the session form) only for the sessions launched asking for it"""

    def __init__(self, directory: Path, manager_url: str, name: str, admin_token: Optional[str],
                 no_agent: Callable[[], bool], automatic: bool = True, poll: float = 2.0):
        self.directory, self.manager_url, self.name = directory.resolve(), manager_url, name
        self.admin_token, self.no_agent, self.automatic, self.poll = admin_token, no_agent, automatic, poll
        self.proc, self.rushes, self.started = None, None, 0.0
        self.launched_unrecorded = False
        # a recording stopped from the page: --record does not start another one before the next session
        self.hold = False
        # the server's reports directory of the session being recorded: its video is copied there
        self.session_reports = None
        self.last = None   # what the last recorder gave: {"state": "done" | "failed", ...}
        self.stopping = threading.Event()
        self.lock = threading.Lock()

    def start(self) -> None:
        # the first recorder waits for a poll: the manager must answer when it attaches
        self.directory.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._loop, name="recording", daemon=True).start()

    def recording(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def session_launched(self) -> None:
        self.hold = False
        if not self.recording():
            self.launched_unrecorded = True

    def start_now(self) -> bool:
        """the page's record button: False if a recording is already going"""
        if self.recording() or self.launched_unrecorded:
            return False
        self.session_launched()
        return True

    def stop_current(self) -> bool:
        """the page's stop button: the recording going ends and is edited; False if none is going"""
        with self.lock:
            if not self.recording():
                return False
            self.hold = True
            os.killpg(self.proc.pid, signal.SIGINT)
            logm.console.log(f"🎬 recording stopped from the manager's page; its video is being edited into {self.rushes / VIDEOS[0]}")
            return True

    def note_reports(self, path: str) -> None:
        # the first one of the recording: a repeated session gives one per session, the recording follows the first
        if self.recording() and self.session_reports is None:
            self.session_reports = path

    def state(self) -> dict:
        if self.proc is not None:
            # ended but not yet taken in hand by the loop (its video still to be copied): still editing
            log = self._log()
            shot = not self.recording() or (log.exists() and SHOT_LINE in log.read_text(errors="replace"))
            return {"state": "editing" if shot else "recording", "rushes": str(self.rushes), "automatic": self.automatic}
        if self.launched_unrecorded:
            return {"state": "starting", "automatic": self.automatic}
        return {**(self.last or {"state": "idle"}), "automatic": self.automatic}

    def _log(self) -> Path:
        return self.rushes.with_name(self.rushes.name + ".log")

    def _loop(self) -> None:
        while not self.stopping.wait(self.poll):
            with self.lock:
                if self.recording() or self.stopping.is_set():
                    continue
                if self.proc is not None:
                    started = self._ended()
                    self.proc = None
                    if not started and self.automatic:
                        return
                if not self.no_agent():
                    # agents registered since the stop: their drop makes a new session, recorded again
                    self.hold = False
                if (self.automatic and self.no_agent() and not self.hold) or self.launched_unrecorded:
                    self._launch()

    def _launch(self) -> None:
        self.launched_unrecorded, self.session_reports, self.last = False, None, None
        self.rushes = self.directory / f"rushes-{self.name}-{time.strftime('%Y%m%d-%H%M%S')}"
        log = open(self._log(), "w")
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
        """False: the recorder could not start"""
        code = self.proc.returncode
        video = self.rushes / VIDEOS[0]
        if code == 0:
            kept = self._keep_with_reports()
            self.last = {"state": "done", "rushes": str(self.rushes), "video": str(video) if video.exists() else None, "kept": kept}
            logm.console.log(f"🎬 session recorded: {kept or (video if video.exists() else self.rushes)}")
            return True
        self.last = {"state": "failed", "rushes": str(self.rushes), "log": str(self._log())}
        if time.monotonic() - self.started < FAILED_START:
            logm.console.log(f"⚠️ the recorder could not start (exit {code}): see {self._log()}"
                             + (", recording stops" if self.automatic else ""))
            return False
        logm.console.log(f"⚠️ the recorder ended with an error (exit {code}): see {self._log()}")
        return True

    def _keep_with_reports(self) -> Optional[str]:
        """the video copied into the server's reports directory, when it is on this machine; its path"""
        if not self.session_reports:
            return None
        reports = Path(self.session_reports)
        # a relative path is the server agent's, from a directory the manager does not know
        if not reports.is_absolute() or not reports.is_dir():
            logm.console.log(f"🎬 the server's reports {reports} are not on this machine: the video stays in {self.rushes}")
            return None
        for name in VIDEOS:
            if (self.rushes / name).exists():
                shutil.copy2(self.rushes / name, reports / f"session-{name}")
        return str(reports / f"session-{VIDEOS[0]}")

    def stop(self) -> None:
        """the manager stops: the recorder ends its shooting and edits it, on its own"""
        self.stopping.set()
        with self.lock:
            if self.recording():
                os.killpg(self.proc.pid, signal.SIGINT)
                logm.console.log(f"🎬 the recording ends; its video is being edited into {self.rushes / VIDEOS[0]}")
