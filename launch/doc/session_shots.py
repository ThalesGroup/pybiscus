# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "pyyaml"]
# ///
"""The forms' screenshots of docs/images taken from a real session: the session form in the manager's
page (session_manager_config, session_manager_config2, session_repeat_config), then the server's
and a client's forms the session filled (session_server_config, session_repeat_server_form,
session_server_loggers, session_client1). Nothing is trained: the session is launched, the forms
are captured, everything is stopped.

Run from anywhere (uv on the PATH):
    uv run launch/doc/session_shots.py [output directory, default docs/images]

The hierarchical forms (hier_*) come from the scenario hierarchical-core-edges of record_session.py.
"""

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
VIEWPORT = {"width": 1920, "height": 1200}
BOUQUET = "cortaixlabs-core"
AGENTS = [("cortaixlabs-labs-00", "server", "paris-saclay", 48.7126, 2.1667),
          ("cortaixlabs-labs-01", "client", "lyon-gerland", 45.7325, 4.8339),
          ("cortaixlabs-labs-02", "client", "grenoble-presquile", 45.2049, 5.7024)]


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


def scroll_frame_to(frame, selector, offset=0):
    frame.evaluate("([s, o]) => { document.querySelector(s).scrollIntoView({block: 'start'}); window.scrollBy(0, o); }",
                   [selector, offset])
    frame.wait_for_timeout(600)


def shoot(work, out):
    procs = Processes(work)
    manager_port = free_port()
    manager = f"http://localhost:{manager_port}"
    ports = {name: free_port() for name, *_ in AGENTS}
    try:
        procs.start("manager", ["session_manager", "--port", str(manager_port), "--bouquet", BOUQUET,
                                "--location", AGENTS[0][2], "--geo", f"{AGENTS[0][3]},{AGENTS[0][4]}"])
        wait_for_port(manager_port)
        for name, role, location, lat, lon in AGENTS:
            registration = work / f"registration_{name}.yml"
            registration.write_text(yaml.safe_dump({
                "manager_url": manager, "agent_name": name, "role": role, "agent_url": f"http://localhost:{ports[name]}",
                "bouquet": BOUQUET, "location": location, "organisation": "CortaiX Labs",
                "geo_location": {"type": "coordinates", "latitude": lat, "longitude": lon}}))
            procs.start(f"agent_{name}", ["pybiscus_agent", "--port", str(ports[name]), "--config", str(registration), "--register"])
        for port in ports.values():
            wait_for_port(port)
        log(f"manager {manager}, agents registering")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            new_page = lambda: browser.new_page(viewport=VIEWPORT)
            page = new_page()
            # a min_clients other than the clients registered asks for a confirmation
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(f"{manager}/pybiscus-session/manage")
            page.wait_for_function("() => !document.getElementById('cfg-btn').disabled", timeout=180000)
            # each agent's waiting page follows the session to its configuration form
            tabs = {}
            for name, *_ in AGENTS:
                tabs[name] = new_page()
                tabs[name].goto(f"http://localhost:{ports[name]}/session/agent/registration/waiting")
            page.wait_for_timeout(6000)

            page.click("#cfg-btn")
            page.wait_for_selector("#cfg-body iframe")
            page.wait_for_timeout(3000)
            form = next(f for f in page.frames if "/session/config" in f.url)
            form.evaluate("(o) => set_options(o)", {"model": "MNIST CNN"}); form.wait_for_timeout(1200)
            form.evaluate("(v) => set_values(v)", {"data": "Mnist"}); form.wait_for_timeout(800)
            page.screenshot(path=out / "session_manager_config.png")

            form.evaluate("(o) => set_options(o)", {"data_partition": " ", "data_holdout": " "}); form.wait_for_timeout(1200)
            scroll_frame_to(form, '[data-pybiscus-prefix="data_partition"]')
            page.screenshot(path=out / "session_manager_config2.png")

            # ' ' sets an Optional, '  ' unsets it (the form's names of its two tabs)
            form.evaluate("(o) => set_options(o)", {"data_holdout": "  ", "num_rounds": " ", "repeat": " ", "repeat.every": " "})
            form.wait_for_timeout(1200)
            form.evaluate("(v) => set_values(v)", {"num_rounds": "2", "repeat.every": "3min"}); form.wait_for_timeout(800)
            scroll_frame_to(form, '[data-pybiscus-prefix="data_holdout"]', -50)
            page.screenshot(path=out / "session_repeat_config.png")

            form.click("#launch-session-button")
            server, client = tabs[AGENTS[0][0]], tabs[AGENTS[1][0]]
            server.wait_for_url(lambda u: "/server/config" in u, timeout=120000)
            client.wait_for_url(lambda u: "/client/config" in u, timeout=120000)
            server.wait_for_timeout(3000); client.wait_for_timeout(3000)
            log("session launched, the agents' forms filled")

            server.get_by_text("Server strategy", exact=True).first.click(); server.wait_for_timeout(800)
            server.screenshot(path=out / "session_server_config.png")
            server.get_by_text("Server run", exact=True).first.click(); server.wait_for_timeout(800)
            server.evaluate("() => window.scrollBy(0, 100)"); server.wait_for_timeout(400)
            server.screenshot(path=out / "session_repeat_server_form.png")
            scroll_frame_to(server, '[data-pybiscus-name="server_run.clients_fit_local_epochs"]', -80)
            server.screenshot(path=out / "session_server_loggers.png")
            client.get_by_text("Data", exact=True).first.click(); client.wait_for_timeout(800)
            client.screenshot(path=out / "session_client1.png")
            browser.close()
        log(f"7 screenshots in {out}")
    finally:
        procs.stop()


def main():
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "docs/images"
    out.mkdir(parents=True, exist_ok=True)
    # a neutral name: the forms and the logs show the working directory
    work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-shots-"))
    # the agents read the plugin manifest relative to their working directory
    for linked in ("pybiscus-plugins", "datasets"):
        (work / linked).symlink_to(REPO / linked)
    try:
        shoot(work, out)
    except BaseException:
        log(f"logs kept in {work}")
        raise
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
