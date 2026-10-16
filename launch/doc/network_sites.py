# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "requests"]
# ///
"""The illustration of the network view on several machines (docs/images/network_machines.png): a
core and two edges whose agents register under simulated machine names, the managers with
--machine; the sessions are launched with their Flower ports, without any training (the agents'
addresses are never reached).
    uv run launch/doc/network_sites.py docs/images/network_machines.png
"""
import json, os, signal, socket, subprocess, sys, tempfile, time, urllib.parse
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
H = {"X-Pybiscus": "1"}
work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-", dir="/tmp")); groups = []
def port():
    with socket.socket() as s: s.bind(("", 0)); return s.getsockname()[1]
def start(name, args):
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}; env["PWD"] = str(work)
    p = subprocess.Popen(["uv", "run", "--project", str(REPO), *args], cwd=work, env=env, stdout=open(work / f"{name}.log", "w"),
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True); groups.append(p.pid)
def wait(p):
    for _ in range(120):
        with socket.socket() as s:
            if s.connect_ex(("localhost", p)) == 0: return
        time.sleep(1)
M = {"core": (port(), "site-core"), "edge1": (port(), "site-edge1"), "edge2": (port(), "site-edge2")}
url = lambda b: f"http://localhost:{M[b][0]}"
try:
    start("core", ["session_manager", "--port", str(M["core"][0]), "--bouquet", "core", "--machine", M["core"][1]])
    for b in ("edge1", "edge2"):
        start(b, ["session_manager", "--port", str(M[b][0]), "--bouquet", b, "--machine", M[b][1], "--upper-url", url("core")])
    for b in M: wait(M[b][0])
    agents = [("core", "core-server", "server", "site-core", 5000), ("core", "relay-edge1", "client", "site-core", 5001),
              ("core", "relay-edge2", "client", "site-edge2", 5002), ("edge1", "edge1-server", "server", "site-edge1", 5100),
              ("edge1", "edge1-client1", "client", "edge1-lab", 5101), ("edge2", "edge2-server", "server", "site-edge2", 5200),
              ("edge2", "edge2-client1", "client", "site-edge2", 5201)]
    for b, name, role, machine, p in agents:
        r = requests.post(f"{url(b)}/pybiscus-session/agent", headers=H,
                          json={"name": name, "role": role, "bouquet": b, "agent_url": f"http://{machine}:{p}", "machine": machine})
        assert r.ok, r.text
    for _ in range(30):
        if len(requests.get(f"{url('core')}/pybiscus-session/agents", headers=H).json()["lower_levels"]) == 2: break
        time.sleep(1)
    for lower in ("edge1", "edge2"):
        assert requests.post(f"{url('core')}/pybiscus-session/relays", headers=H, json={"bouquet": lower, "client": f"relay-{lower}"}).ok
    assert requests.post(f"{url('core')}/pybiscus-session/link-transports", headers=H, json={"bouquet": "edge1", "transport": "manager"}).ok
    def run(b, flower_port, host):
        presets = {"options_set": {"model": "MNIST CNN"}, "options_lock": [], "values_lock": [], "num_rounds": "3",
                   "values_set": {"flower_server.listen_address": f"[::]:{flower_port}", "flower_client.server_address": f"{host}:{flower_port}"}}
        r = requests.post(f"{url(b)}/pybiscus-session/run?presets=" + urllib.parse.quote(json.dumps(presets)), headers=H)
        assert r.ok, (b, r.text)
    run("core", 3333, "site-core")
    for b, fp in (("edge1", 3334), ("edge2", 3335)):
        for _ in range(30):
            up = requests.get(f"{url(b)}/pybiscus-session/agents", headers=H).json()["upper_level"]
            if up and (up.get("session") or {}).get("link"): break
            time.sleep(1)
        run(b, fp, M[b][1])
    time.sleep(8)
    view = requests.get(f"{url('core')}/pybiscus-session/network.json", headers=H).json()
    print(len(view["machines"]), "machines", len(view["processes"]), "processes", len(view["flows"]), "flows", "problems", view["problems"])
    with sync_playwright() as pw:
        b = pw.chromium.launch(); page = b.new_page(viewport={"width": 2400, "height": 900})
        page.goto(f"{url('core')}/pybiscus-session/network"); page.wait_for_timeout(3000)
        page.screenshot(path=sys.argv[1], full_page=True); b.close()
finally:
    for g in groups:
        try: os.killpg(g, signal.SIGTERM)
        except ProcessLookupError: pass
