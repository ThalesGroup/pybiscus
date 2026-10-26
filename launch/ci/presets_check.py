# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "requests", "pyyaml"]
# ///
"""The session's presets applied by an agent's form (in the browser) and by an agent launched by an
order (pybiscus/session/agent/presets.py, in Python) must give the same configuration.

    uv run launch/ci/presets_check.py [cases.json ...]     (default: launch/ci/presets_cases.json)

Starts an agent in a temporary directory, reads its form's configuration without presets (the base)
and with each case's, then has presets_compare.py apply the same presets to the base in Python and
compare both once validated. A case: {"role": "server" | "client", "presets": {options_set, values_set...}}.
"""

import json
import os
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
MANIFESTS = "pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def form_config(page, base_url: str, path: str) -> dict:
    page.goto(base_url + path)
    page.wait_for_load_state("networkidle")
    rows = page.evaluate("traverseDOM(document.getElementById('top-div'), []).reverse()")
    answer = requests.post(base_url + "/config/json/to_yaml", json=rows, headers={"X-Pybiscus": "1"}, timeout=30)
    answer.raise_for_status()
    return yaml.safe_load(answer.json()["success"])


def main() -> int:
    case_files = sys.argv[1:] or [str(REPO / "launch/ci/presets_cases.json")]
    cases = {name: case for f in case_files for name, case in json.load(open(f)).items()}

    work = Path(tempfile.mkdtemp(prefix="pybiscus-presets-"))
    for plugins in REPO.glob("pybiscus-plugins*"):
        (work / plugins.name).symlink_to(plugins)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    # the configurations' root_dir is ${oc.env:PWD}
    env.update(PWD=str(work), PYBISCUS_PLUGIN_CONF_PATH=MANIFESTS, UV_PROJECT=str(REPO))
    port = free_port()
    base_url = f"http://localhost:{port}"
    agent = subprocess.Popen(["uv", "run", "--project", str(REPO), "pybiscus_agent", "--port", str(port)], cwd=work,
                             env=env, stdout=open(work / "agent.log", "w"), stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(180):
            try:
                requests.get(base_url + "/client/config", timeout=5)
                break
            except requests.RequestException:
                time.sleep(1)
        else:
            print(f"the agent did not start (see {work}/agent.log)")
            return 1

        dump = {"bases": {}, "cases": {}}
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            for name, case in cases.items():
                role = case["role"]
                if role not in dump["bases"]:
                    dump["bases"][role] = form_config(page, base_url, f"/{role}/config")
                query = urllib.parse.urlencode({"presets": json.dumps(case["presets"])})
                dump["cases"][name] = {**case, "form": form_config(page, base_url, f"/{role}/config?{query}")}
            browser.close()
        (work / "form.json").write_text(json.dumps(dump, indent=1))
    finally:
        try:
            os.killpg(agent.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    return subprocess.run(["uv", "run", "--project", str(REPO), "python", str(REPO / "launch/ci/presets_compare.py"),
                           str(work / "form.json")], cwd=work, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
