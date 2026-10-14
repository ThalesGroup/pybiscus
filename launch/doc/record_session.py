# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "requests", "pyyaml"]
# ///
"""Record a session as seen from the session manager's page: a time-lapse video for the docs.

Run from the repository root (ffmpeg on the PATH):
    uv run launch/doc/record_session.py launch/doc/scenarios/mnist-session.yml

A session manager and the scenario's agents start on free ports in a working directory of their
own, the scenario registers the agents, configures the server's session, launches every agent and
waits for their runs to end, while the manager's page is captured with a caption telling the
current step. The captures are then assembled: each caption stays long enough to be read, the
training rounds scroll by. Outputs: <output>.mp4, <output>.webp, and with png the frames.
The scenario file and the options are described in docs/recording.md.

Playwright is pinned to the version of the Chromium in ~/.cache/ms-playwright; another version
asks for its own (uv run --with playwright==<version> playwright install chromium).
"""

import argparse
import itertools
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

REPO = Path(__file__).resolve().parents[2]
H = {"X-Pybiscus": "1"}
ENDED = ("success", "failure", "stopped")

CAPTION_JS = """(t) => { let d = document.getElementById('__caption');
  if (!d) { d = document.createElement('div'); d.id = '__caption';
    d.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;padding:10px 22px;' +
      'border-radius:10px;background:rgba(20,24,40,.88);color:#fff;font:600 22px system-ui,sans-serif;' +
      'box-shadow:0 4px 18px rgba(0,0,0,.35);white-space:nowrap';
    document.body.appendChild(d); }
  d.textContent = t; d.style.display = t ? 'block' : 'none'; }"""

CHECK_DONE_JS = """() => { const s = document.getElementById('check-success-result'), f = document.getElementById('check-failure-result');
  return (s && s.offsetParent) || (f && f.offsetParent); }"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


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


class Recorder:
    """captures the manager's page with the current caption; Playwright's sync API is not thread-safe,
    so the frames are taken between the scenario's actions"""

    def __init__(self, page, frames, period):
        self.page, self.frames, self.period, self.caption, self.n = page, frames, period, "", 0
        frames.mkdir(parents=True)
        self.index = open(frames / "captions.tsv", "w")

    def shoot(self, count=1):
        for _ in range(count):
            self.page.evaluate(CAPTION_JS, self.caption)
            name = f"f{self.n:05d}.png"
            self.page.screenshot(path=self.frames / name)
            self.index.write(f"{name}\t{self.caption}\n"); self.index.flush()
            self.n += 1
            self.page.wait_for_timeout(int(self.period * 1000))

    def say(self, caption, hold):
        self.caption = caption
        log(caption)
        self.shoot(hold)


def run_scenario(sc, work, frames):
    rounds = int(sc["session"]["values"]["num_rounds"])
    captions, hold = sc["captions"], sc.get("hold", {})
    viewport = sc.get("viewport", {"width": 1440, "height": 900})
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
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # opened before anything happens: the manager's log buffer is emptied by the page that reads it
            page = browser.new_page(viewport=viewport)
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
                current = page.evaluate("() => (document.getElementById('round-num') || {}).textContent || ''").strip()
                rec.caption = captions["round"].format(round=current or "…", rounds=rounds)
                if current != shown:
                    log(rec.caption); shown = current
                rec.shoot()
                status = [requests.get(f"http://localhost:{a['port']}/run/status", headers=H).json().get("status") for a in agents]
                if all(s in ENDED for s in status):
                    break
                if time.time() > deadline:
                    raise SystemExit(f"the runs did not end within {sc.get('timeout', 1800)} s: {status}")
            if any(s != "success" for s in status):
                raise SystemExit(f"a run did not succeed: {dict(zip((a['name'] for a in agents), status))} (logs in {work})")
            # the last round's metrics reach the page shortly after the runs end
            page.wait_for_timeout(2000)
            accuracy = page.evaluate("() => (document.getElementById('acc-test') || {}).textContent || ''").strip()
            rec.say(captions["finished"].format(accuracy=accuracy, rounds=rounds), hold.get("finished", 12))
            browser.close()
    finally:
        procs.stop()


def assemble(frames, output, formats, timing):
    rows = [line.rstrip("\n").split("\t") for line in open(frames / "captions.tsv")]
    groups = [(caption, [f for f, _ in g]) for caption, g in itertools.groupby(rows, key=lambda r: r[1])]
    lines = []
    for i, (caption, names) in enumerate(groups):
        last = i == len(groups) - 1
        # each round has its own caption: the rounds are told by the fixed beginning of theirs
        rolling = bool(timing["round_prefix"]) and caption.startswith(timing["round_prefix"])
        per = timing["round_frame"] if rolling else max(timing["min_frame"], (timing["last_caption"] if last else timing["caption"]) / len(names))
        for name in names:
            lines += [f"file '{frames / name}'", f"duration {per:.3f}"]
    final = frames / groups[-1][1][-1]
    lines += [f"file '{final}'", f"duration {timing['end_hold']}", f"file '{final}'"]
    concat = frames / "concat.txt"
    concat.write_text("\n".join(lines) + "\n")
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat)]
    output.parent.mkdir(parents=True, exist_ok=True)
    if "mp4" in formats:
        subprocess.run(ff + ["-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "24", "-preset", "slow",
                             "-movflags", "+faststart", f"{output}.mp4"], check=True)
    if "webp" in formats:
        subprocess.run(ff + ["-vf", f"fps=10,scale={timing['webp_width']}:-1:flags=lanczos", "-c:v", "libwebp_anim",
                             "-lossless", "0", "-q:v", "70", "-loop", "0", f"{output}.webp"], check=True)
    if "png" in formats:
        shutil.copytree(frames, f"{output}-frames", dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path, help="basename of the outputs (default: the scenario's)")
    # not TMPDIR: the working directory appears in the server log the page shows, it must be short and neutral
    parser.add_argument("--work-root", type=Path, default=Path("/tmp"))
    parser.add_argument("--keep", action="store_true", help="keep the working directory (logs, frames, experiments)")
    args = parser.parse_args()

    sc = yaml.safe_load(args.scenario.read_text())
    output = (args.output or Path(sc["output"])).resolve()
    formats = sc.get("formats", ["mp4", "webp"])
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is needed to assemble the video: install it first (Debian: apt install ffmpeg)")
    timing = {"caption": 2.2, "last_caption": 4.0, "min_frame": 0.25, "round_frame": 0.12, "end_hold": 2.5,
              "webp_width": 1080, "round_prefix": sc["captions"]["round"].split("{")[0], **sc.get("timing", {})}

    work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-", dir=args.work_root))
    for plugins in REPO.glob("pybiscus-plugins*"):
        (work / plugins.name).symlink_to(plugins)
    (work / "datasets").symlink_to(REPO / "datasets")
    log(f"working directory {work}")
    try:
        run_scenario(sc, work, work / "frames")
        assemble(work / "frames", output, formats, timing)
        for fmt in formats:
            path = f"{output}-frames" if fmt == "png" else f"{output}.{fmt}"
            log(f"{path} written")
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
