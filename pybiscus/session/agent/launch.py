"""The run of an agent started with --accept-launch, launched by the manager's order: the session's
presets, asked of the manager as the waiting page asks them, applied to the launch configuration as
the form applies them, then checked and started as the form's buttons do."""

import os
import threading
from typing import Optional

import requests
import yaml

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.agent.pybiscus_agent as pybagent
from pybiscus.session.agent import presets
from pybiscus.session.auth import headers_for

MODEL_NAMES = {"server": "ConfigServer", "client": "ConfigClient"}
# a launch takes seconds (the check): a second order meanwhile would find no run going yet
_launching = threading.Lock()


def _model(role: str):
    if role == "server":
        from pybiscus.flower_config.config_server import ConfigServer
        return ConfigServer
    from pybiscus.flower_config.config_client import ConfigClient
    return ConfigClient


def base_config(role: str) -> dict:
    if pybagent.launch_config:
        with open(pybagent.launch_config, encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    return presets.defaults(_model(role))


def session_params() -> dict:
    manager_url = pybagent.registration_parameters["manager_url"].rstrip("/")
    url = f"{manager_url}/pybiscus-session/params"
    answer = requests.get(url, params={"agent": pybagent.registration_parameters.get("name", "")},
                          headers=headers_for(url), timeout=10)
    params = answer.json()
    if answer.status_code != 200 or params.get("status") != "success":
        raise ValueError(f"the manager gave no session parameters: {params.get('message', answer.status_code)}")
    return params


def _answer(result) -> tuple[int, dict]:
    response, code = result if isinstance(result, tuple) else (result, 200)
    return code, response.get_json() or {}


def launch() -> dict:
    if not _launching.acquire(blocking=False):
        return {"done": False, "reason": "a launch is already in progress"}
    try:
        return _launch()
    finally:
        _launching.release()


def _launch() -> dict:
    role = pybagent.registration_parameters.get("role")
    if not pybagent.accept_launch:
        return {"done": False, "reason": "this agent was not started with --accept-launch"}
    if role not in MODEL_NAMES:
        return {"done": False, "reason": "this agent is not registered"}
    from pybiscus.session.agent.run_session import run_session
    if run_session.is_running():
        return {"done": False, "reason": "its run is still going"}
    try:
        params = session_params()
        config, unplaced, ignored = presets.apply(_model(role), base_config(role), params.get("presets") or {})
    except (requests.RequestException, ValueError, OSError, yaml.YAMLError) as error:
        return {"done": False, "reason": str(error)}
    # what the manager imposes is read nowhere else: no one looks at a form
    logm.console.log(f"🚀 run launched by the manager's order, its presets: {params.get('presets')}")
    if ignored:
        logm.console.log(f"⚠️ values imposed by the manager ignored, they call an interpolation resolver: {', '.join(ignored)}")
    if unplaced:
        logm.console.log(f"presets without a place in this {role}'s configuration: {', '.join(unplaced)}")

    pybagent.session_server_url = params.get("server_url")
    path = os.path.join(pybagent.upload_folder, f"{MODEL_NAMES[role]}.yml")
    with open(path, "w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False)
    pybagent.uploaded_file_path = path

    with pybagent.rest_server.app_context():
        code, checked = _answer(pybagent.checkConfigurationFile(role, path))
        if code != 200:
            fields = "; ".join(f"{'.'.join(map(str, f.get('loc', [])))}: {f.get('msg', '')}"
                               for f in checked.get("fields") or [])
            return {"done": False, "reason": f"its configuration does not pass the check: {checked.get('error', '')}"
                                              + (f" ({fields})" if fields else "")}
        from pybiscus.session.agent.routes import clientsession, serversession
        code, started = _answer(serversession.server() if role == "server" else clientsession.client())
    if code != 202:
        return {"done": False, "reason": started.get("error", f"its run did not start ({code})")}
    return {"done": True}


def waiting_for_order() -> Optional[str]:
    """the waiting page's explanation for an agent the manager launches"""
    if not pybagent.accept_launch:
        return None
    source = f"the presets applied to {pybagent.launch_config}" if pybagent.launch_config else "the presets applied to the form's defaults"
    return f"The manager launches this agent's run when the session is launched: its configuration is {source}."
