# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "pyyaml"]
# ///
"""docs/images/session_evaluation.png from a real session of the manager: the session form set to the
evaluation of an ONNX model (purpose evaluation, the model's file and hash, an exact F1), the agents'
runs launched by order from their forms' defaults, the manager's page once the session has finished.
Exits non-zero when the session did not give its per-site report.

Run from anywhere (uv on the PATH), after launch/uv/onnx_eval/prepare.sh:
    uv run launch/doc/evaluation_shot.py [model.onnx, default experiments/published/mnist_cnn.onnx] [output directory, default docs/images]
"""

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
VIEWPORT = {"width": 1600, "height": 900}
AGENTS = [("server", "server", "Organiser"), ("client_1", "client", "Site A"), ("client_2", "client", "Site B")]


def log(message):
    sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {message}\n")


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
        self.env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYBISCUS_PLUGIN_CONF_PATH")}
        # the forms show root_dir as ${oc.env:PWD}: the working directory, not the caller's
        self.env["UV_PROJECT"], self.env["PWD"] = str(REPO), str(work)

    def start(self, name, args):
        p = subprocess.Popen(["uv", "run", "--project", str(REPO), *args], cwd=self.work, env=self.env,
                             stdin=subprocess.DEVNULL, stdout=open(self.work / f"{name}.log", "w"),
                             stderr=subprocess.STDOUT, start_new_session=True)
        self.groups.append(p.pid)

    def stop(self):
        for group in self.groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass


def report_problems(work) -> list[str]:
    reports = sorted(work.glob("experiments/**/evaluation.json"))
    if not reports:
        return ["no evaluation.json in the server's reports"]
    last = json.loads(reports[-1].read_text())["rounds"][-1]
    problems = []
    if len(last["sites"]) != 2:
        problems.append(f"{len(last['sites'])} site(s) in the report, 2 expected")
    if "f1_macro" not in (last.get("weighted_mean") or {}).get("metrics", {}):
        problems.append("no f1_macro in the sites' weighted mean")
    if "Training Finished" in (work / "agent_client_1.log").read_text(errors="replace"):
        problems.append("a client trained")
    return problems


def shoot(work, out, model, sha256):
    procs = Processes(work)
    manager_port = free_port()
    manager = f"http://localhost:{manager_port}"
    ports = {name: free_port() for name, *_ in AGENTS}
    try:
        procs.start("manager", ["session_manager", "--port", str(manager_port)])
        wait_for_port(manager_port)
        for name, role, location in AGENTS:
            registration = work / f"registration_{name}.yml"
            registration.write_text(yaml.safe_dump({
                "manager_url": manager, "agent_name": name, "role": role, "agent_url": f"http://localhost:{ports[name]}",
                "location": location, "organisation": location,
                "geo_location": {"type": "coordinates", "latitude": 48.71, "longitude": 2.2}}))
            # no --launch-config: the session's presets apply to the forms' defaults, nothing else says evaluation
            procs.start(f"agent_{name}", ["pybiscus_agent", "--port", str(ports[name]), "--config", str(registration),
                                          "--register", "--accept-launch"])
        for port in ports.values():
            wait_for_port(port)
        log(f"manager {manager}, agents registering")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, color_scheme="dark")
            page.goto(f"{manager}/pybiscus-session/manage")
            page.wait_for_function("() => !document.getElementById('cfg-btn').disabled", timeout=180000)
            page.wait_for_timeout(6000)

            page.click("#cfg-btn")
            page.wait_for_selector("#cfg-body iframe")
            page.wait_for_timeout(3000)
            form = next(f for f in page.frames if "/session/config" in f.url)
            # ' ' sets an Optional (the form's name of its tab holding a value)
            # each site validates on examples held out of its own share: two sites, two results
            form.evaluate("(o) => set_options(o)", {"model": "ONNX model (evaluation only)", "model.config.num_classes": " ",
                                                    "data_partition": " ", "data_holdout": " "})
            form.wait_for_timeout(1200)
            form.evaluate("(v) => set_values(v)", {"purpose": "evaluation", "data": "Mnist", "model.config.path": str(model),
                                                   "model.config.sha256": sha256, "model.config.num_classes": "10",
                                                   "model.config.class_rates": "per_class"})
            form.wait_for_timeout(800)
            form.click("#launch-session-button")
            log("session launched")
            page.wait_for_function("() => document.body.innerText.toLowerCase().includes('session finished')", timeout=600000)
            page.wait_for_timeout(5000)
            page.screenshot(path=out / "session_evaluation.png")
            browser.close()
        problems = report_problems(work)
        if problems:
            raise SystemExit("the evaluation session went wrong: " + "; ".join(problems))
        log(f"{out / 'session_evaluation.png'}")
    finally:
        procs.stop()


def main():
    model = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "experiments/published/mnist_cnn.onnx"
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else REPO / "docs/images"
    if not model.is_file():
        raise SystemExit(f"no {model}: launch/uv/onnx_eval/prepare.sh publishes the MNIST session's model")
    out.mkdir(parents=True, exist_ok=True)
    # a neutral name: the manager's page shows the reports' directory
    work = Path(tempfile.mkdtemp(prefix="pybiscus-shots-")) / "pybiscus-evaluation-demo"
    work.mkdir()
    # the agents read the plugin manifest relative to their working directory
    for linked in ("pybiscus-plugins", "datasets"):
        (work / linked).symlink_to(REPO / linked)
    published = work / "experiments/published" / model.name
    published.parent.mkdir(parents=True)
    shutil.copyfile(model, published)
    try:
        shoot(work, out, published, hashlib.sha256(published.read_bytes()).hexdigest())
    except BaseException:
        log(f"logs kept in {work}")
        raise
    shutil.rmtree(work.parent)


if __name__ == "__main__":
    main()
