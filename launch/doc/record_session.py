# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "requests", "pyyaml"]
# ///
"""Record a session as seen from the session manager's page: a time-lapse video for the docs.

Run from the repository root (ffmpeg on the PATH):
    uv run launch/doc/record_session.py launch/doc/scenarios/mnist-session.yml
    uv run launch/doc/record_session.py --attach http://localhost:5555 --output docs/videos/my-session

With a scenario, a session manager and the scenario's agents start on free ports in a working
directory of their own, the scenario registers the agents, configures the server's session,
launches every agent and waits for their runs to end. With --attach, the tool drives nothing: it
follows a session someone runs, from its manager's state, until the runs end (or Ctrl+C). In both
modes the manager's page is captured with a caption telling the current step, and the captures are
assembled: each caption stays long enough to be read, the rounds and the waits scroll by.
Outputs: <output>.mp4, <output>.webp, and with png the frames. See docs/recording.md.

Playwright is pinned to the version of the Chromium in ~/.cache/ms-playwright; another version
asks for its own (uv run --with playwright==<version> playwright install chromium).
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

import requests
import yaml
from playwright.sync_api import sync_playwright

from sessioncapture import EVENT, FINAL, PROGRESS, Recorder, assemble, log, page_text

REPO = Path(__file__).resolve().parents[2]
H = {"X-Pybiscus": "1"}
RUN_ENDED = ("success", "failure", "stopped")
# AgentState (pybiscus/session/agent/agent_weblog.py), as the manager's /pybiscus-session/agents gives them
AGENT_ENDED = ("terminated", "failed", "stopped")

DEFAULT_VIEWPORT = {"width": 1440, "height": 900}

ATTACH_CAPTIONS = {
    "waiting": "Waiting for the agents: {count} registered",
    "registered": "Agent {name} registers ({role}, {location})",
    "started": "The session starts",
    "joined": "Recording joins the running session: {count} agents",
    "validated": "{name}: configuration checked",
    "executing": "{name}: run launched",
    "round": "Federated training: round {round}{of_rounds}",
    "failed": "{name}: run {state}",
    "finished": "Session finished: test accuracy {accuracy}",
    "dropped": "The session was dropped",
    "interrupted": "Recording stopped",
}
ATTACH_HOLD = {"registered": 5, "started": 4, "joined": 5, "validated": 3, "executing": 3, "failed": 5, "final": 12}

CHECK_DONE_JS = """() => { const s = document.getElementById('check-success-result'), f = document.getElementById('check-failure-result');
  return (s && s.offsetParent) || (f && f.offsetParent); }"""


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_port(port, limit=180):
    end = time.time() + limit
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("localhost", port)) == 0:
                return
        time.sleep(1)
    raise SystemExit(f"nothing listens on port {port} after {limit} s")


class Processes:
    """the manager and the agents, each in its own process group, stopped together"""

    def __init__(self, work):
        self.work, self.groups = work, []
        # the script runs in its own environment: the agents' `uv run pybiscus` must use the repository's
        self.env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYBISCUS_PLUGIN_CONF_PATH")}
        self.env["UV_PROJECT"] = str(REPO)
        # the configurations' root_dir is ${oc.env:PWD}: inherited, it would point the reports at the caller's directory
        self.env["PWD"] = str(work)

    def start(self, name, args):
        out = open(self.work / f"{name}.log", "w")
        p = subprocess.Popen(["uv", "run", "--project", str(REPO), *args], cwd=self.work, env=self.env,
                             stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        self.groups.append(p.pid)

    def stop(self):
        for group in self.groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass


def run_scenario(sc, work, frames):
    rounds = int(sc["session"]["values"]["num_rounds"])
    captions, hold = sc["captions"], sc.get("hold", {})
    viewport = sc.get("viewport", DEFAULT_VIEWPORT)
    # the captured page alone: its layout stays the viewport's, its pixels are multiplied
    scale = sc.get("scale", 1)
    procs = Processes(work)
    manager_port, flower_port = free_port(), free_port()
    agents = [{**a, "port": free_port()} for a in sc["agents"]]
    m = sc["manager"]
    procs.start("manager", ["session_manager", "--port", str(manager_port), "--bouquet", m["bouquet"],
                            "--location", m["location"], "--geo", ",".join(map(str, m["geo"]))])
    for a in agents:
        procs.start(f"agent_{a['name']}", ["pybiscus_agent", "--port", str(a["port"])])
    try:
        for port in (manager_port, *(a["port"] for a in agents)):
            wait_for_port(port)
        manager = f"http://localhost:{manager_port}"
        log(f"manager {manager}")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=viewport, device_scale_factor=scale)
            page.goto(f"{manager}/pybiscus-session/manage"); page.wait_for_timeout(3000)
            rec = Recorder(page, frames, sc.get("period", 0.35))
            rec.say(captions["empty"], hold.get("empty", 8))

            for a in agents:
                lat, lon = a["geo"]
                meta = {"name": a["name"], "role": a["role"], "bouquet": m["bouquet"], "location": a["location"],
                        "geo_location": {"type": "coordinates", "latitude": lat, "longitude": lon},
                        "organisation": sc.get("organisation", "pybiscus-demo")}
                url = f"http://localhost:{a['port']}"
                assert requests.post(f"{manager}/pybiscus-session/agent", headers=H, json={**meta, "agent_url": url}).ok
                assert requests.post(f"{url}/session/agent/registration", headers=H, json={**meta, "manager_url": manager}).ok
                rec.say(captions["registered"].format(**a), hold.get("registered", 5))

            rec.say(captions["configured"].format(rounds=rounds), hold.get("configured", 4))
            server = next(a for a in agents if a["role"] == "server")
            form = browser.new_page(viewport=viewport)
            presets = {"values_set": {"flower_server.server_port": flower_port}, "values_lock": []}
            form.goto(f"http://localhost:{server['port']}/session/config?presets=" + urllib.parse.quote(json.dumps(presets)))
            form.wait_for_timeout(1500)
            form.evaluate("(o) => set_options(o)", sc["session"]["options"]); form.wait_for_timeout(1200)
            form.evaluate("(v) => set_values(v)", sc["session"]["values"]); form.wait_for_timeout(300)
            form.evaluate("""() => { window.__sc = null; window.addEventListener('message',
                e => { if (e.data && e.data.type === 'session_config') window.__sc = e.data.value; }); }""")
            form.click("#launch-session-button"); form.wait_for_timeout(500)
            session_config = form.evaluate("window.__sc"); form.close()
            r = requests.post(f"{manager}/pybiscus-session/run?presets=" + urllib.parse.quote(json.dumps(session_config)), headers=H)
            if not r.ok:
                raise SystemExit(f"the manager refused the session: {r.status_code} {r.text}")
            rec.say(captions["started"], hold.get("started", 3))

            for a in agents:
                agent_page = browser.new_page(viewport=viewport)
                agent_page.goto(f"http://localhost:{a['port']}/session/agent/registration/waiting")
                agent_page.wait_for_url(lambda u: "/config?" in u, timeout=60000); agent_page.wait_for_timeout(2500)
                agent_page.click("#check-config-button")
                agent_page.wait_for_function(CHECK_DONE_JS, timeout=60000)
                if not agent_page.evaluate("() => !!document.getElementById('check-success-result').offsetParent"):
                    raise SystemExit(f"{a['name']}: its configuration does not pass the check (see {work}/agent_{a['name']}.log)")
                agent_page.click("#execute-button"); agent_page.wait_for_timeout(1000); agent_page.close()
                rec.say(captions["launched"].format(**a), hold.get("launched", 3))

            shown = None
            deadline = time.time() + sc.get("timeout", 1800)
            while True:
                current = page_text(page, "round-num")
                caption = captions["round"].format(round=current or "…", rounds=rounds)
                if current != shown:
                    log(caption); shown = current
                rec.shoot(caption)
                status = [requests.get(f"http://localhost:{a['port']}/run/status", headers=H).json().get("status") for a in agents]
                if all(s in RUN_ENDED for s in status):
                    break
                if time.time() > deadline:
                    raise SystemExit(f"the runs did not end within {sc.get('timeout', 1800)} s: {status}")
            if any(s != "success" for s in status):
                raise SystemExit(f"a run did not succeed: {dict(zip((a['name'] for a in agents), status))} (logs in {work})")
            # the last round's metrics reach the page shortly after the runs end
            page.wait_for_timeout(2000)
            accuracy = page_text(page, "acc-test")
            rec.say(captions["finished"].format(accuracy=accuracy, rounds=rounds), hold.get("finished", 12), FINAL)
            browser.close()
    finally:
        procs.stop()


def attach(url, sc, frames, max_duration):
    """follows the session of the manager at url, from its state, until its runs end"""
    parsed = urllib.parse.urlsplit(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    token = urllib.parse.parse_qs(parsed.query).get("token", [None])[0]
    # the manager's administration token, required beyond the loopback: in the page's URL once, then a cookie
    headers = {**H, **({"Authorization": f"Bearer {token}"} if token else {})}
    captions = {**ATTACH_CAPTIONS, **sc.get("captions", {})}
    hold = {**ATTACH_HOLD, **sc.get("hold", {})}

    def manager_state():
        r = requests.get(f"{base}/pybiscus-session/agents", headers=headers, timeout=10)
        if r.status_code in (401, 403):
            raise SystemExit(f"the manager asks for its token: --attach '{base}?token=<its administration token>'")
        r.raise_for_status()
        return r.json()

    first = manager_state()
    # Ctrl+C ends the recording, which is then assembled: it must not end the browser first
    interrupted = []
    signal.signal(signal.SIGINT, lambda *_: interrupted.append(True))
    with sync_playwright() as p:
        browser = p.chromium.launch(handle_sigint=False)
        page = browser.new_page(viewport=sc.get("viewport", DEFAULT_VIEWPORT), device_scale_factor=sc.get("scale", 1))
        page.goto(f"{base}/pybiscus-session/manage" + (f"?token={urllib.parse.quote(token)}" if token else ""))
        page.wait_for_timeout(3000)
        rec = Recorder(page, frames, sc.get("period", 0.35))
        # what happened before the recording is the starting point, not news to caption
        known = set(first["servers"]) | set(first["clients"])
        states = dict(first.get("states") or {})
        executed = {name for name, state in states.items() if state == "executing" or state in AGENT_ENDED}
        running, shown = bool(first.get("session_running")), None
        deadline = time.time() + max_duration if max_duration else None
        log(f"attached to {base}: Ctrl+C stops the recording")
        if running:
            rec.say(captions["joined"].format(count=len(known)), hold["joined"])
        while True:
            if interrupted:
                rec.say(captions["interrupted"], hold["final"], FINAL)
                break
            d = manager_state()
            for role in ("server", "client"):
                for name in d[f"{role}s"]:
                    if name not in known:
                        known.add(name)
                        meta = d.get("meta", {}).get(name, {})
                        rec.say(captions["registered"].format(name=name, role=role, location=meta.get("location", "")),
                                hold["registered"])
            now_running = bool(d.get("session_running"))
            if now_running and not running:
                rec.say(captions["started"], hold["started"])
            if running and not now_running and not (executed and all(states.get(n) in AGENT_ENDED for n in executed)):
                rec.say(captions["dropped"], hold["final"], FINAL)
                break
            running = now_running
            for name, state in (d.get("states") or {}).items():
                if states.get(name) == state:
                    continue
                states[name] = state
                if state in ("validated", "executing"):
                    if state == "executing":
                        executed.add(name)
                    rec.say(captions[state].format(name=name), hold[state])
                elif state in ("failed", "stopped"):
                    rec.say(captions["failed"].format(name=name, state=state), hold["failed"])
            if executed and all(states.get(n) in AGENT_ENDED for n in executed) \
                    and not any(s in ("validating", "validated", "executing") for s in states.values()):
                # the last round's metrics reach the page shortly after the runs end
                page.wait_for_timeout(2000)
                rec.say(captions["finished"].format(accuracy=page_text(page, "acc-test")), hold["final"], FINAL)
                break
            if executed:
                current = page_text(page, "round-num")
                total = (d.get("session") or {}).get("constraints", {}).get("num_rounds")
                caption = captions["round"].format(round=current or "…", of_rounds=f" / {total}" if total else "")
            else:
                caption = captions["waiting"].format(count=len(known))
            if caption != shown:
                log(caption); shown = caption
            rec.shoot(caption, PROGRESS)
            if deadline and time.time() > deadline:
                interrupted.append(True)
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", type=Path, nargs="?",
                        help="scenario file; with --attach, optional: its output, formats, viewport, scale, period, captions, hold, timing")
    parser.add_argument("--attach", metavar="MANAGER_URL", help="record the session of a running manager, without driving it")
    parser.add_argument("--max-duration", type=float, help="with --attach: stop recording after this many seconds")
    parser.add_argument("--output", type=Path, help="basename of the outputs (default: the scenario's)")
    parser.add_argument("--viewport", metavar="WIDTHxHEIGHT", help="size of the captured page, instead of the scenario's (default 1440x900)")
    parser.add_argument("--scale", type=float, help="pixel density of the captures: 2 gives a 2880x1800 video of a 1440x900 page")
    # not TMPDIR: the working directory appears in the server log the page shows, it must be short and neutral
    parser.add_argument("--work-root", type=Path, default=Path("/tmp"))
    parser.add_argument("--keep", action="store_true", help="keep the working directory (logs, frames, experiments)")
    args = parser.parse_args()
    if not args.scenario and not args.attach:
        parser.error("a scenario, or --attach")

    sc = yaml.safe_load(args.scenario.read_text()) if args.scenario else {}
    if args.viewport:
        try:
            width, height = (int(v) for v in args.viewport.lower().split("x"))
        except ValueError:
            parser.error(f"--viewport {args.viewport}: WIDTHxHEIGHT expected, such as 1920x1080")
        sc["viewport"] = {"width": width, "height": height}
    if args.scale:
        sc["scale"] = args.scale
    default_output = f"experiments/recordings/session-{time.strftime('%Y%m%d-%H%M%S')}" if args.attach else None
    output = args.output or sc.get("output") or default_output
    if output is None:
        parser.error("the scenario gives no output: --output")
    output = Path(output).resolve()
    formats = sc.get("formats", ["mp4", "webp"])
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is needed to assemble the video: install it first (Debian: apt install ffmpeg)")

    work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-", dir=args.work_root))
    log(f"working directory {work}")
    try:
        if args.attach:
            attach(args.attach, sc, work / "frames", args.max_duration)
        else:
            for plugins in REPO.glob("pybiscus-plugins*"):
                (work / plugins.name).symlink_to(plugins)
            (work / "datasets").symlink_to(REPO / "datasets")
            run_scenario(sc, work, work / "frames")
        assemble(work / "frames", output, formats, sc.get("timing"))
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
