# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "requests", "pyyaml", "pillow"]
# ///
"""Shoot a Pybiscus session (its manager's and agents' pages), then edit the rushes into a video or
screenshots for the docs.

Run from the repository root (ffmpeg on the PATH):
    uv run launch/doc/record_session.py shoot launch/doc/scenarios/mnist-session.yml
    uv run launch/doc/record_session.py shoot --attach http://localhost:5555
    uv run launch/doc/record_session.py edit <rushes directory> launch/doc/scenarios/mnist-session.cut.yml

shoot plays a scenario (it starts a manager and its agents, registers them, configures and launches
the session) or, with --attach, follows a session someone runs, and captures every page with the
events it goes through. edit composes the scenes of a cut (main view, inset, caption, pace) and
the screenshots it names; it can be run again on the same rushes with another cut. A scenario
naming its cut is edited right after it is shot. The rushes, the scenario and the cut are
described in docs/recording.md; the shooting and the editing themselves are in launch/doc/rushes/,
which knows nothing of Pybiscus.

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

from rushes import Shooting, edit, log

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = Path(__file__).resolve().parent / "scenarios"
H = {"X-Pybiscus": "1"}
RUN_ENDED = ("success", "failure", "stopped")
# AgentState (pybiscus/session/agent/agent_weblog.py), as the manager's /pybiscus-session/agents gives them
AGENT_ENDED = ("terminated", "failed", "stopped")
DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
# the window of an agent's tab once its run is launched, narrow so that its run monitor stays readable as an inset
INSET_VIEWPORT = {"width": 760, "height": 470}
# the panels whose position each capture keeps, for the cut to show one of them: the map, the agents,
# the accuracy curves, the cycles of the manager's page; the log of an agent's run monitor
MANAGER_PANELS = ("geo", "nodes", "accChart", "cyclesChart")
AGENT_PANELS = ("console",)

CHECK_DONE_JS = """() => { const s = document.getElementById('check-success-result'), f = document.getElementById('check-failure-result');
  return (s && s.offsetParent) || (f && f.offsetParent); }"""


def manager_label(bouquet=None):
    return lambda page: f"session manager{f' · {bouquet}' if bouquet else ''}"


def agent_label(name):
    def label(page):
        path = page.url.split("?")[0]
        what = ("run monitor" if path.endswith("/run") else "registration" if "registration" in path
                else "session form" if path.endswith("/session/config") else "configuration form")
        return f"{name} · {what}"
    return label


def page_text(page, element_id):
    return (page.evaluate(f"() => (document.getElementById('{element_id}') || {{}}).textContent || ''") or "").strip()


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
    """the managers and the agents, each in its own process group, stopped together"""

    def __init__(self, work, manifests=None):
        self.work, self.groups = work, []
        # the script runs in its own environment: the agents' `uv run pybiscus` must use the repository's
        self.env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYBISCUS_PLUGIN_CONF_PATH")}
        self.env["UV_PROJECT"] = str(REPO)
        # the configurations' root_dir is ${oc.env:PWD}: inherited, it would point the reports at the caller's directory
        self.env["PWD"] = str(work)
        if manifests:
            # relative to the working directory, which links the plugin directories
            self.env["PYBISCUS_PLUGIN_CONF_PATH"] = ":".join(manifests)

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


def check_and_launch(tab, name, work, shooting=None):
    tab.click("#check-config-button")
    tab.wait_for_function(CHECK_DONE_JS, timeout=60000)
    if not tab.evaluate("() => !!document.getElementById('check-success-result').offsetParent"):
        raise SystemExit(f"{name}: its configuration does not pass the check (see {work}/agent_{name}.log)")
    if shooting:
        shooting.tick(2)
    tab.click("#execute-button"); tab.wait_for_timeout(1000)


def fill_session_form(form, options, values, shooting=None):
    if options:
        form.evaluate("(o) => set_options(o)", options); form.wait_for_timeout(1200)
        if shooting:
            shooting.tick(2)
    if values:
        form.evaluate("(v) => set_values(v)", values); form.wait_for_timeout(300)
        if shooting:
            shooting.tick(2)


def session_config(form):
    form.evaluate("""() => { window.__sc = null; window.addEventListener('message',
        e => { if (e.data && e.data.type === 'session_config') window.__sc = e.data.value; }); }""")
    form.click("#launch-session-button"); form.wait_for_timeout(500)
    return form.evaluate("window.__sc")


def run_session(manager, config, who):
    r = requests.post(f"{manager}/pybiscus-session/run?presets=" + urllib.parse.quote(json.dumps(config)), headers=H)
    if not r.ok:
        raise SystemExit(f"{who}: the manager refused the session: {r.status_code} {r.text}")


# ............................................................................. a simple session

def shoot_scenario(sc, work, rushes):
    """events: empty, registered, configured, started, launched, round (round, rounds, turn: the client
    whose turn it is, one per round), finished (accuracy, rounds)"""
    rounds = int(sc["session"]["values"]["num_rounds"])
    viewport = sc.get("viewport", DEFAULT_VIEWPORT)
    scale = sc.get("scale", 1)
    procs = Processes(work, sc.get("plugin_manifests"))
    manager_port, flower_port = free_port(), free_port()
    agents = [{**a, "port": free_port()} for a in sc["agents"]]
    clients = [a["name"] for a in agents if a["role"] == "client"]
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
            new_page = lambda: browser.new_page(viewport=viewport, device_scale_factor=scale)
            shooting = Shooting(rushes, viewport, scale, sc.get("period", 0.35))
            page = new_page()
            page.goto(f"{manager}/pybiscus-session/manage"); page.wait_for_timeout(3000)
            shooting.add_view("manager", page, MANAGER_PANELS, manager_label())
            shooting.set_focus("manager")
            shooting.event("empty"); shooting.tick(4)

            # each agent is registered through its own registration form, as a person does
            for a in agents:
                tab, view = new_page(), f"agent:{a['name']}"
                url = f"http://localhost:{a['port']}"
                tab.goto(f"{url}/session/agent/registration"); tab.wait_for_timeout(1000)
                shooting.add_view(view, tab, AGENT_PANELS, agent_label(a["name"]))
                shooting.set_focus("manager", view)
                lat, lon = a["geo"]
                for field, value in (("managerUrl", manager), ("name", a["name"]), ("baseUrl", url), ("bouquet", m["bouquet"]),
                                     ("location", a["location"]), ("organisation", sc.get("organisation", "pybiscus-demo"))):
                    tab.fill(f"#{field}", value)
                tab.click("#coordsToggle")
                tab.fill("#latitude", str(lat)); tab.fill("#longitude", str(lon))
                tab.select_option("#role", a["role"])
                shooting.event("registered", name=a["name"], role=a["role"], location=a["location"])
                shooting.tick(2)
                tab.click("#submitBtn")
                tab.wait_for_url(lambda u: "/registration/waiting" in u, timeout=30000)
                # the manager's map shows the new agent once its page has polled the registrations
                shooting.tick(4)

            server = next(a for a in agents if a["role"] == "server")
            form = new_page()
            presets = {"values_set": {"flower_server.server_port": flower_port}, "values_lock": []}
            form.goto(f"http://localhost:{server['port']}/session/config?presets=" + urllib.parse.quote(json.dumps(presets)))
            form.wait_for_timeout(1500)
            shooting.add_view("session-form", form, (), agent_label(server["name"]))
            shooting.set_focus("manager", "session-form")
            shooting.event("configured", rounds=rounds); shooting.tick(1)
            fill_session_form(form, sc["session"]["options"], sc["session"]["values"], shooting)
            config = session_config(form)
            shooting.remove_view("session-form"); form.close()
            run_session(manager, config, m["bouquet"])
            shooting.set_focus("manager")
            shooting.event("started"); shooting.tick(3)

            for a in agents:
                view = f"agent:{a['name']}"
                tab = shooting.views[view]["page"]
                tab.wait_for_url(lambda u: "/config?" in u, timeout=60000); tab.wait_for_timeout(2500)
                shooting.set_focus("manager", view)
                shooting.event("launched", name=a["name"], role=a["role"], location=a["location"]); shooting.tick(1)
                check_and_launch(tab, a["name"], work, shooting)
                tab.goto(f"http://localhost:{a['port']}/run"); tab.wait_for_timeout(800)
                shooting.tick(2)
                # from now on the tab is only an inset
                tab.set_viewport_size(sc.get("inset_viewport", INSET_VIEWPORT))

            shooting.set_focus("manager", *(f"agent:{c}" for c in clients))
            shown, deadline = None, time.time() + sc.get("timeout", 1800)
            while True:
                current = page_text(page, "round-num")
                if current != shown:
                    turn = clients[(int(current) - 1) % len(clients)] if current.isdigit() and int(current) > 0 and clients else (clients or [""])[0]
                    shooting.event("round", round=current or "…", rounds=rounds, turn=turn)
                    log(f"round {current or '…'} / {rounds}"); shown = current
                shooting.tick()
                status = [requests.get(f"http://localhost:{a['port']}/run/status", headers=H).json().get("status") for a in agents]
                if all(s in RUN_ENDED for s in status):
                    break
                if time.time() > deadline:
                    raise SystemExit(f"the runs did not end within {sc.get('timeout', 1800)} s: {status}")
            if any(s != "success" for s in status):
                raise SystemExit(f"a run did not succeed: {dict(zip((a['name'] for a in agents), status))} (logs in {work})")
            # the agents' last states and the last round's metrics reach the page shortly after the runs end
            for _ in range(20):
                states = requests.get(f"{manager}/pybiscus-session/agents", headers=H).json().get("states") or {}
                if all(states.get(a["name"]) in AGENT_ENDED for a in agents):
                    break
                shooting.tick()
            page.wait_for_timeout(2000)
            accuracy = page_text(page, "acc-test")
            shooting.set_focus("manager")
            shooting.event("finished", accuracy=accuracy, rounds=rounds); shooting.tick(4)
            log(f"session finished, test accuracy {accuracy}")
            browser.close()
    finally:
        procs.stop()


# ......................................................................... a hierarchical session

def shoot_hierarchical(sc, work, rushes):
    """a tree of sessions, one manager per bouquet; events: registered, relays, session-form (bouquet),
    form (name), round (round, rounds, turn: the lower bouquet whose turn it is, one per round), end,
    tab (tab: a tab a take opened, the pages captured after it); the scenario's takes (whole pages, a
    panel after a click) at their steps"""
    rounds = int(sc["session"]["values"]["num_rounds"])
    takes = sc.get("takes", [])
    viewport = sc.get("viewport", {"width": 1500, "height": 1250})
    form_viewport = sc.get("form_viewport", {"width": 1500, "height": 950})
    managers = {m["bouquet"]: {**m, "port": free_port(), "flower": free_port()} for m in sc["managers"]}
    root = next(b for b, m in managers.items() if not m.get("upper"))
    children = {b: [c for c, m in managers.items() if m.get("upper") == b] for b in managers}
    order, queue = [], [root]
    while queue:
        order.append(queue.pop(0)); queue += children[order[-1]]
    agents = [{**a, "port": free_port()} for a in sc["agents"]]
    servers = {a["bouquet"]: a for a in agents if a["role"] == "server"}
    url = lambda b: f"http://localhost:{managers[b]['port']}"
    procs = Processes(work, sc.get("plugin_manifests"))
    for b in order:
        m = managers[b]
        upper = ["--upper-url", url(m["upper"])] if m.get("upper") else []
        procs.start(f"manager_{b}", ["session_manager", "--port", str(m["port"]), "--bouquet", b, "--location", m["location"],
                                     "--geo", ",".join(map(str, m["geo"])), *upper])
    for a in agents:
        procs.start(f"agent_{a['name']}", ["pybiscus_agent", "--port", str(a["port"])])
    try:
        for port in [m["port"] for m in managers.values()] + [a["port"] for a in agents]:
            wait_for_port(port)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            shooting = Shooting(rushes, viewport, 1, sc.get("period", 0.35))
            # a page per manager filmed only: each one costs a few hundred MB, next to the runs of a large tree
            filmed = [b for b in order if b in sc.get("film", order)]
            if root not in filmed:
                raise SystemExit(f"film: the root manager {root} is the one the rounds are read on, it must be filmed")
            for b in filmed:
                page = browser.new_page(viewport=viewport)
                page.goto(f"{url(b)}/pybiscus-session/manage")
                shooting.add_view(f"manager:{b}", page, MANAGER_PANELS, manager_label(b))
            managers_in_focus = [f"manager:{b}" for b in filmed]
            shooting.set_focus(*managers_in_focus)
            time.sleep(3)

            def step(kind, **fields):
                shooting.event(kind, **fields)
                # the pages as the event leaves them, before a take clicks in one of them
                shooting.tick(2)
                at = ":".join([kind, *map(str, fields.values())])
                for take in (t for t in takes if t["at"] == at):
                    tab, _, panel = take["view"].partition("@")
                    page = shooting.views[tab]["page"]
                    if take.get("tab"):
                        page.click(f"#mid-tabs .tool[data-tab={take['tab']}]"); page.wait_for_timeout(800)
                    if take.get("click_text"):
                        # a tab of a form, which shows the section the take is about
                        page.get_by_text(take["click_text"], exact=True).first.click(); page.wait_for_timeout(800)
                    shooting.take(take["name"], page, take.get("full_page", False), panel or None)
                    if take.get("tab"):
                        # the page now shows that tab: a cut can end on it
                        shooting.event("tab", tab=take["tab"]); shooting.tick(3)

            for i, a in enumerate(agents):
                b = a["bouquet"]
                # a relay runs on the machine of the server it stands for: it is placed there
                place = managers[a["relay_for"]] if a.get("relay_for") else managers[b]
                lat, lon = a.get("geo") or (place["geo"][0] + 0.02 * (i % 3) - (0.04 if a.get("relay_for") else 0),
                                            place["geo"][1] + 0.03 * (i % 3) - (0.06 if a.get("relay_for") else 0))
                meta = {"name": a["name"], "role": a["role"], "bouquet": b, "location": a.get("location", place["location"]),
                        "geo_location": {"type": "coordinates", "latitude": lat, "longitude": lon},
                        "organisation": sc.get("organisation", "pybiscus-demo")}
                agent_url = f"http://localhost:{a['port']}"
                assert requests.post(f"{url(b)}/pybiscus-session/agent", headers=H, json={**meta, "agent_url": agent_url}).ok
                assert requests.post(f"{agent_url}/session/agent/registration", headers=H, json={**meta, "manager_url": url(b)}).ok
                shooting.tick()
            for b in order:
                for _ in range(60):
                    known = {l.get("bouquet") for l in requests.get(f"{url(b)}/pybiscus-session/agents", headers=H).json()["lower_levels"]}
                    if set(children[b]) <= known:
                        break
                    shooting.tick()
                else:
                    raise SystemExit(f"{b}: its lower levels {children[b]} did not report to it")
            shooting.tick(6)
            step("registered")

            for a in agents:
                if a.get("relay_for"):
                    view = shooting.views.get(f"manager:{a['bouquet']}")
                    # a manager not filmed gets a page just for the designation
                    page = view["page"] if view else browser.new_page(viewport=viewport)
                    if not view:
                        page.goto(f"{url(a['bouquet'])}/pybiscus-session/manage"); page.wait_for_timeout(3000)
                    page.select_option(f'select.relay-select[data-bouquet="{a["relay_for"]}"]', a["name"])
                    shooting.tick(3)
                    if not view:
                        page.close()
            shooting.tick(6)
            step("relays")

            form = browser.new_page(viewport=form_viewport)
            shooting.add_view("session-form", form, (), lambda page: "session form")
            shooting.set_focus(*managers_in_focus, "session-form")

            def launch_session(b, presets, options=None, values=None):
                form.goto(f"http://localhost:{servers[b]['port']}/session/config?presets=" + urllib.parse.quote(json.dumps(presets)))
                form.wait_for_timeout(1500)
                fill_session_form(form, options, values)
                step("session-form", bouquet=b)
                run_session(url(b), session_config(form), b)
                log(f"{b}: session started")

            launch_session(root, {"values_set": {"flower_server.server_port": managers[root]["flower"]}, "values_lock": []},
                           sc["session"]["options"], sc["session"]["values"])
            for b in order[1:]:
                for _ in range(30):
                    up = requests.get(f"{url(b)}/pybiscus-session/agents", headers=H).json()["upper_level"]
                    if up and (up.get("session") or {}).get("link"):
                        break
                    time.sleep(1)
                else:
                    raise SystemExit(f"{b}: no link from its upper level")
                # the lower level's form opens with its upper level's choices set and locked, as its manager gives them
                constraints = up["session"]["constraints"]
                model, model_values = constraints.get("model"), constraints.get("model_values", {})
                plain = {k: v for k, v in constraints.items() if k not in ("model", "model_values")}
                tabs = {"model": model, **{k: " " for k in plain if k == "num_rounds"}}
                presets = {"options_set": tabs, "options_lock": list(tabs),
                           "values_set": {**plain, **model_values, "flower_server.server_port": managers[b]["flower"]},
                           "values_lock": list(plain) + list(model_values)}
                launch_session(b, presets, sc.get("lower_session", {}).get("options"), sc.get("lower_session", {}).get("values"))
            shooting.remove_view("session-form"); form.close()
            shooting.set_focus(*managers_in_focus)

            # servers from the top down, then the clients, then the relays: a relay's level waits for its lower one
            ordered = sorted(agents, key=lambda a: (0 if a["role"] == "server" else 2 if a.get("relay_for") else 1,
                                                     order.index(a["bouquet"])))
            for a in ordered:
                tab, view = browser.new_page(viewport=form_viewport), f"agent:{a['name']}"
                tab.goto(f"http://localhost:{a['port']}/session/agent/registration/waiting")
                tab.wait_for_url(lambda u: "/config?" in u, timeout=60000); tab.wait_for_timeout(2500)
                shooting.add_view(view, tab, AGENT_PANELS, agent_label(a["name"]))
                shooting.set_focus(*managers_in_focus, view)
                step("form", name=a["name"])
                check_and_launch(tab, a["name"], work)
                # the agents' tabs are closed once launched: nine of them, with the runs, would exhaust the memory
                shooting.remove_view(view); tab.close()
                log(f"{a['name']}: launched")

            def done(levels):
                return all(len(l.get("cycles", [])) >= rounds and done(l.get("lower_levels", [])) for l in levels)
            deadline, shown = time.time() + sc.get("timeout", 1800), None
            lowers = children[root]
            root_page = shooting.views[f"manager:{root}"]["page"]
            while True:
                current = page_text(root_page, "round-num")
                if current != shown:
                    turn = lowers[(int(current) - 1) % len(lowers)] if current.isdigit() and int(current) > 0 and lowers else (lowers or [""])[0]
                    shooting.event("round", round=current or "…", rounds=rounds, turn=turn)
                    log(f"round {current or '…'} / {rounds}"); shown = current
                d = requests.get(f"{url(root)}/pybiscus-session/agents", headers=H).json()
                if len(d.get("cycles", [])) >= rounds and done(d.get("lower_levels", [])):
                    break
                if time.time() > deadline:
                    raise SystemExit(f"the levels did not end their {rounds} rounds within {sc.get('timeout', 1800)} s (logs in {work})")
                shooting.tick()
            # the last round's metrics and states reach the pages shortly after
            time.sleep(8)
            log(f"{rounds} rounds on every level")
            step("end")
            browser.close()
    finally:
        procs.stop()


# ..................................................................... a session run by someone

def shoot_attached(url, sc, rushes, max_duration):
    """follows the session of the manager at url, from its state, until its runs end; events:
    attached or joined (count), registered, started, validated, executing, round (round, rounds,
    of_rounds), failed (name, state), finished (accuracy), dropped, interrupted, lost (the manager
    no longer answers)"""
    parsed = urllib.parse.urlsplit(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    token = urllib.parse.parse_qs(parsed.query).get("token", [None])[0]
    # the manager's administration token, required beyond the loopback: in the page's URL once, then a cookie
    headers = {**H, **({"Authorization": f"Bearer {token}"} if token else {})}

    def manager_state():
        try:
            r = requests.get(f"{base}/pybiscus-session/agents", headers=headers, timeout=10)
        except requests.ConnectionError:
            return None
        if r.status_code in (401, 403):
            raise SystemExit(f"the manager asks for its token: --attach '{base}?token=<its administration token>'")
        r.raise_for_status()
        return r.json()

    first = manager_state()
    if first is None:
        raise SystemExit(f"no session manager answers at {base}")
    # Ctrl+C ends the shooting, which is then kept and edited: it must not end the browser first
    interrupted = []
    signal.signal(signal.SIGINT, lambda *_: interrupted.append(True))
    viewport, scale = sc.get("viewport", DEFAULT_VIEWPORT), sc.get("scale", 1)
    with sync_playwright() as p:
        browser = p.chromium.launch(handle_sigint=False)
        page = browser.new_page(viewport=viewport, device_scale_factor=scale)
        page.goto(f"{base}/pybiscus-session/manage" + (f"?token={urllib.parse.quote(token)}" if token else ""))
        page.wait_for_timeout(3000)
        shooting = Shooting(rushes, viewport, scale, sc.get("period", 0.35))
        shooting.add_view("manager", page, MANAGER_PANELS, manager_label())
        shooting.set_focus("manager")
        # what happened before the shooting is the starting point, not news
        known = set(first["servers"]) | set(first["clients"])
        states = dict(first.get("states") or {})
        executed = {name for name, state in states.items() if state == "executing" or state in AGENT_ENDED}
        running, shown = bool(first.get("session_running")), None
        shooting.event("joined" if running else "attached", count=len(known))
        log(f"attached to {base}: Ctrl+C stops the shooting")
        deadline = time.time() + max_duration if max_duration else None
        while True:
            if interrupted:
                shooting.event("interrupted"); shooting.tick(2)
                break
            d = manager_state()
            if d is None:
                # the manager stopped: what was shot until then is kept and edited
                shooting.event("lost")
                break
            for role in ("server", "client"):
                for name in d[f"{role}s"]:
                    if name not in known:
                        known.add(name)
                        shooting.event("registered", name=name, role=role, location=d.get("meta", {}).get(name, {}).get("location", ""))
            now_running = bool(d.get("session_running"))
            if now_running and not running:
                shooting.event("started")
            if running and not now_running and not (executed and all(states.get(n) in AGENT_ENDED for n in executed)):
                shooting.event("dropped"); shooting.tick(2)
                break
            running = now_running
            for name, state in (d.get("states") or {}).items():
                if states.get(name) != state:
                    states[name] = state
                    if state in ("validated", "executing"):
                        if state == "executing":
                            executed.add(name)
                        shooting.event(state, name=name)
                    elif state in ("failed", "stopped"):
                        shooting.event("failed", name=name, state=state)
            if executed and all(states.get(n) in AGENT_ENDED for n in executed) \
                    and not any(s in ("validating", "validated", "executing") for s in states.values()):
                # the last round's metrics reach the page shortly after the runs end
                page.wait_for_timeout(2000)
                shooting.event("finished", accuracy=page_text(page, "acc-test")); shooting.tick(4)
                break
            if executed:
                current = page_text(page, "round-num")
                if current != shown:
                    total = (d.get("session") or {}).get("constraints", {}).get("num_rounds")
                    shooting.event("round", round=current or "…", rounds=total or "", of_rounds=f" / {total}" if total else "")
                    shown = current
            shooting.tick()
            if deadline and time.time() > deadline:
                interrupted.append(True)
        browser.close()


# ............................................................................................ CLI

def edit_with(rushes, cut_file, output):
    cut = yaml.safe_load(Path(cut_file).read_text())
    if output and cut.get("shots") and not cut.get("scenes"):
        # a cut of screenshots only: --output is their directory
        cut["shots_dir"] = str(output)
        output = None
    edit(rushes, cut, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    shoot = sub.add_parser("shoot", help="play a scenario, or follow a running session, and keep its rushes")
    shoot.add_argument("scenario", type=Path, nargs="?", help="scenario file (optional with --attach: its viewport, scale, period, cut)")
    shoot.add_argument("--attach", metavar="MANAGER_URL", help="follow the session of a running manager, without driving it")
    shoot.add_argument("--max-duration", type=float, help="with --attach: stop after this many seconds")
    shoot.add_argument("--rushes", type=Path, help="directory of the rushes (default: experiments/recordings/rushes-<name>-<date>)")
    shoot.add_argument("--cut", help="cut to edit right after the shooting, instead of the scenario's (\"none\": no editing)")
    shoot.add_argument("--output", type=Path, help="with a cut: basename of the video, or directory of the screenshots, instead of the cut's")
    shoot.add_argument("--viewport", metavar="WIDTHxHEIGHT", help="size of the captured pages, instead of the scenario's (default 1440x900)")
    shoot.add_argument("--scale", type=float, help="pixel density of the captures: 2 gives 2880x1800 images of a 1440x900 page")
    # not TMPDIR: the working directory appears in the server log the pages show, it must be short and neutral
    shoot.add_argument("--work-root", type=Path, default=Path("/tmp"))
    shoot.add_argument("--keep", action="store_true", help="keep the working directory (the processes' logs, experiments)")
    edit_parser = sub.add_parser("edit", help="edit rushes with a cut: the scenes into a video, the screenshots")
    edit_parser.add_argument("rushes", type=Path)
    edit_parser.add_argument("cut", type=Path)
    edit_parser.add_argument("--output", type=Path, help="basename of the video, or directory of the screenshots, instead of the cut's")
    args = parser.parse_args()

    if args.command == "edit":
        if shutil.which("ffmpeg") is None:
            raise SystemExit("ffmpeg is needed to edit the video: install it first (Debian: apt install ffmpeg)")
        return edit_with(args.rushes, args.cut, args.output)

    if not args.scenario and not args.attach:
        parser.error("shoot: a scenario, or --attach")
    sc = yaml.safe_load(args.scenario.read_text()) if args.scenario else {}
    if args.viewport:
        try:
            width, height = (int(v) for v in args.viewport.lower().split("x"))
        except ValueError:
            parser.error(f"--viewport {args.viewport}: WIDTHxHEIGHT expected, such as 1920x1080")
        sc["viewport"] = {"width": width, "height": height}
    if args.scale:
        sc["scale"] = args.scale
    name = args.scenario.stem if args.scenario and not args.attach else "attached"
    rushes = (args.rushes or Path(f"experiments/recordings/rushes-{name}-{time.strftime('%Y%m%d-%H%M%S')}")).resolve()
    if rushes.exists() and any(rushes.iterdir()):
        parser.error(f"--rushes {rushes}: not empty")
    cut_file = args.cut or sc.get("cut") or (str(SCENARIOS / "attach.cut.yml") if args.attach else None)
    if cut_file == "none":
        cut_file = None
    if cut_file and shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is needed to edit the video: install it first (Debian: apt install ffmpeg), or --cut none")

    if args.attach:
        shoot_attached(args.attach, sc, rushes, args.max_duration)
    else:
        work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-", dir=args.work_root))
        log(f"working directory {work}")
        for plugins in REPO.glob("pybiscus-plugins*"):
            (work / plugins.name).symlink_to(plugins)
        (work / "datasets").symlink_to(REPO / "datasets")
        try:
            (shoot_hierarchical if sc.get("kind") == "hierarchical" else shoot_scenario)(sc, work, rushes)
        finally:
            if not args.keep:
                shutil.rmtree(work, ignore_errors=True)
    log(f"rushes in {rushes}")
    if cut_file:
        edit_with(rushes, cut_file, args.output)


if __name__ == "__main__":
    sys.exit(main())
