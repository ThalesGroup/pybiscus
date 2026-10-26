"""A session of the manager without any browser: agents started with --register --accept-launch
register by themselves (before their manager listens), the session is launched through the manager's
API, the agents' runs are launched by order and finish.

    session_check.py <work dir> <launch configs dir> <rounds> <timeout s>

The launch configurations are the smoke run's (server.yml, client_1.yml, client_2.yml: CPU, few
samples); the session's presets apply over them as over an operator's form.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import requests
import yaml

REPO = Path(__file__).resolve().parents[2]
work, configs, rounds, timeout = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), int(sys.argv[3]), int(sys.argv[4])
AGENTS = {"server": "server", "client_1": "client", "client_2": "client"}
# no token is required on the loopback, the header is (CSRF)
HEADERS = {"X-Pybiscus": "1"}

env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYBISCUS_PLUGIN_CONF_PATH")}
env["UV_PROJECT"] = str(REPO)
# the configurations' root_dir is ${oc.env:PWD}: the reports go to the work directory
env["PWD"] = str(work)
# rich wraps its lines at the console's width, the file:line column cutting a sentence searched for
env["COLUMNS"] = "300"
groups = []
failed = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(name, args):
    log = open(work / f"{name}.log", "w")
    process = subprocess.Popen(["uv", "run", "--project", str(REPO), *args], cwd=work, env=env, stdout=log,
                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    groups.append(process.pid)
    return process


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def log_of(name) -> str:
    return " ".join((work / f"{name}.log").read_text(errors="replace").split())


def wait(condition, limit):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(1)
    return None


def judge(ok: bool, message: str, detail: str = "") -> bool:
    if ok:
        print(f"  ok       {message}", flush=True)
    else:
        print(f"  FAILED   {message}{f' ({detail})' if detail else ''}", flush=True)
        failed.append(message)
    return ok


manager_port, flower_port = free_port(), free_port()
ports = {name: free_port() for name in AGENTS}
manager = f"http://localhost:{manager_port}"


def registration(name, role, port) -> str:
    path = work / f"registration-{name}-{port}.yml"
    path.write_text(yaml.safe_dump({"manager_url": manager, "agent_name": name, "agent_url": f"http://localhost:{port}",
                                    "role": role, "location": "smoke", "organisation": "smoke",
                                    "geo_location": {"type": "coordinates", "latitude": 48.71, "longitude": 2.2}}))
    return str(path)


def agents_listing():
    try:
        return requests.get(f"{manager}/pybiscus-session/agents", headers=HEADERS, timeout=5).json()
    except (requests.RequestException, ValueError):
        return None


INTRUDER = """
import sys
import numpy as np
import flwr as fl
from pybiscus.flower import clientauth
if sys.argv[2] != "-":
    clientauth.present_client_token(sys.argv[2], "0" * 64)

class Intruder(fl.client.NumPyClient):
    def get_parameters(self, config):
        return []

try:
    fl.client.start_client(server_address=f"localhost:{sys.argv[1]}", client=Intruder().to_client(), insecure=True)
    print("INTRUDER ACCEPTED")
except Exception as error:
    print("INTRUDER", getattr(error, "code", lambda: type(error).__name__)())
"""


def intrude(as_name: str) -> str:
    """a Flower client launched outside the session: without a credential, or a forged one"""
    script = work / "intruder.py"
    script.write_text(INTRUDER)
    done = subprocess.run(["uv", "run", "--project", str(REPO), "python", str(script), str(flower_port), as_name],
                          cwd=work, env=env, capture_output=True, text=True, timeout=120)
    return done.stdout + done.stderr


def listening(port: int) -> bool:
    with socket.socket(socket.AF_INET6) as s:
        return s.connect_ex(("::1", port)) == 0


def run_states() -> dict:
    states = {}
    for name, port in ports.items():
        try:
            states[name] = requests.get(f"http://localhost:{port}/run/status", timeout=5).json().get("status")
        except (requests.RequestException, ValueError):
            states[name] = None
    return states


try:
    alone = subprocess.run(["uv", "run", "--project", str(REPO), "pybiscus_agent", "--port", str(free_port()), "--register"],
                           cwd=work, env=env, capture_output=True, text=True, timeout=300)
    judge(alone.returncode == 2 and "--register needs" in alone.stderr, "--register without a configuration is refused",
          f"exit {alone.returncode}")

    for name, role in AGENTS.items():
        start(name, ["pybiscus_agent", "--port", str(ports[name]), "--config", registration(name, role, ports[name]),
                     "--register", "--accept-launch", "--launch-config", str(configs / f"{name}.yml")])
    # the plugins load first: a minute or two on a loaded machine
    judge(wait(lambda: all("registering again" in log_of(name) for name in AGENTS), 300),
          "the agents started before their manager register again", f"see {work}/<agent>.log")

    start("manager", ["session_manager", "--port", str(manager_port)])
    listing = wait(lambda: (lambda d: d if d and set(d["clients"]) == {"client_1", "client_2"} and "server" in d["servers"]
                            else None)(agents_listing()), 120)
    if not judge(bool(listing), "the three agents registered by themselves", f"see {work}/manager.log"):
        raise SystemExit(1)
    meta = listing["meta"]
    judge(all(meta[name]["accept_launch"] for name in AGENTS)
          and meta["client_1"]["geo_location"] == {"latitude": 48.71, "longitude": 2.2} and meta["client_1"]["machine"],
          "their registrations carry the launch by order, their place and machine", json.dumps(meta))

    # the same name under another URL: refused once, and the registered agent left as it is
    other = free_port()
    duplicate = start("duplicate", ["pybiscus_agent", "--port", str(other),
                                    "--config", registration("client_1", "client", other), "--register"])
    refused = wait(lambda: "refused the registration of client_1" in log_of("duplicate"), 300)
    stop(duplicate)
    kept = (agents_listing() or {}).get("meta", {}).get("client_1", {})
    judge(bool(refused) and kept.get("accept_launch") and kept.get("agent_url") == f"http://localhost:{ports['client_1']}",
          "a registration under a name taken is refused and leaves the registered agent", json.dumps(kept))

    presets = {"options_set": {"model": "MNIST CNN", "data": "Mnist"}, "options_lock": ["model", "data"],
               "values_set": {"flower_server.listen_address": f"[::1]:{flower_port}",
                              "flower_client.server_address": f"localhost:{flower_port}", "manager_url": manager},
               "values_lock": [], "num_rounds": rounds}
    launched = requests.post(f"{manager}/pybiscus-session/run?presets=" + urllib.parse.quote(json.dumps(presets)),
                             headers=HEADERS, timeout=30)
    if not judge(launched.ok, "the session is launched through the manager's API", launched.text):
        raise SystemExit(1)

    # while the server waits for its clients or trains: they load their data first
    if judge(bool(wait(lambda: listening(flower_port), 300)), "the session's Flower server listens"):
        for as_name, what in (("-", "without a credential"), ("client_1", "with a forged credential of client_1")):
            out = intrude(as_name)
            judge("UNAUTHENTICATED" in out and "INTRUDER ACCEPTED" not in out,
                  f"a Flower client launched outside the session, {what}, is refused", out.strip()[-300:])

    ended = wait(lambda: (lambda s: s if all(v in ("success", "failure", "stopped") for v in s.values()) else None)(run_states()),
                 timeout)
    states = ended or run_states()
    judge(bool(ended) and all(v == "success" for v in states.values()), "the three runs launched by order succeed",
          f"{states}, see {work}/<agent>.log")
    judge(f"[ROUND {rounds}]" in log_of("server"), f"the server reached round {rounds}", f"see {work}/server.log")
    judge(any(work.glob("experiments/**/final_checkpoint.pt")), "a final checkpoint", f"none under {work}/experiments")
    tracebacks = [name for name in [*AGENTS, "manager"] if "Traceback (most recent call last)" in log_of(name)]
    judge(not tracebacks, "no traceback", f"in {', '.join(tracebacks)}")
    judge("Flower clients authenticated" in log_of("server")
          and all("presenting the session's credential" in log_of(name) for name in ("client_1", "client_2")),
          "the runs of the session authenticate their Flower clients")
finally:
    for group in groups:
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass

sys.exit(1 if failed else 0)
