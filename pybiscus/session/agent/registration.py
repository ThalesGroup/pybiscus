"""The registration of an agent with its manager: from its page (the form posts it to the manager, then
to the agent), or by the agent itself at its start (--register), without a browser."""

import threading
import time
from typing import Optional

import requests

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.agent.pybiscus_agent as pybagent
from pybiscus.session.auth import session_token_for, set_session_token
from pybiscus.session.csrf import HEADER

RETRY_S = 5


def adopt(parameters: dict) -> None:
    """the agent registered: its states go to this manager, its runs present the session token,
    it asks this manager for its orders under this name"""
    from pybiscus.session.agent.pybiscus_agent import reset_registration, reset_session
    # a new registration starts a new session
    reset_session()
    reset_registration()
    invitation = pybagent.agent_invitation
    if invitation is not None:
        # the invitation's identity is the one the manager accepts, whatever the page sent
        parameters.update({"name": invitation.agent_name, "role": invitation.role, "manager_url": invitation.manager_url,
                           "session_token": invitation.token, **({"bouquet": invitation.bouquet} if invitation.bouquet else {})})
    pybagent.registration_parameters = parameters
    set_session_token(parameters.get("session_token"))
    if parameters.get("manager_url"):
        from pybiscus.session.agent import orders
        from pybiscus.session.agent.agent_weblog import initAgentLogger
        initAgentLogger(f"{parameters['manager_url'].rstrip('/')}/webhook/agents", parameters.get("bouquet"), parameters.get("name"))
        orders.follow(parameters["manager_url"], parameters.get("name"), pybagent.call_token)


def geo_location(config: dict):
    """as the page sends it: coordinates, or a text"""
    geo = config.get("geo_location")
    if not isinstance(geo, dict):
        return geo if geo is not None else config.get("location")
    if geo.get("type") == "coordinates":
        return {"latitude": float(geo["latitude"]), "longitude": float(geo["longitude"])}
    return geo.get("text") or config.get("location")


class Refused(Exception):
    """the manager answered no: asking again would get the same answer"""


def headers(token: Optional[str], manager_url: str) -> dict:
    token = token or session_token_for(manager_url)
    return {HEADER: "1", **({"Authorization": f"Bearer {token}"} if token else {})}


def manager_bouquet(manager_url: str, token: Optional[str]) -> Optional[str]:
    """the bouquet of the manager's session, which the page sets and locks before registering"""
    answer = requests.get(f"{manager_url}/pybiscus-session/identity", headers=headers(token, manager_url), timeout=10)
    return answer.json().get("bouquet") if answer.ok else None


def register(config: dict, agent_url: str) -> str:
    """one registration with the manager of this registration configuration, as the page does it;
    its message, or Refused"""
    from pybiscus.session.agent.machine import machine_name, physical_cores
    manager_url = config["manager_url"].rstrip("/")
    token = config.get("session_token")
    bouquet = config.get("bouquet") or manager_bouquet(manager_url, token)
    payload = {
        "application": "Pybiscus",
        "name": config["agent_name"],
        "agent_url": config.get("agent_url") or agent_url,
        "bouquet": bouquet,
        "location": config.get("location"),
        "geo_location": geo_location(config),
        "organisation": config.get("organisation"),
        "role": config["role"],
        "machine": machine_name(),
        "cpu_cores": physical_cores(),
        "call_token": pybagent.call_token,
        "accept_launch": pybagent.accept_launch,
    }
    answer = requests.post(f"{manager_url}/pybiscus-session/agent", json=payload,
                           headers=headers(token, manager_url), timeout=10)
    try:
        body = answer.json()
    except ValueError:
        body = {}
    message = body.get("message") or f"HTTP {answer.status_code}"
    # a manager starting or overloaded may answer 5xx: asked again; any 4xx is its answer
    if 400 <= answer.status_code < 500:
        raise Refused(message)
    if not answer.ok:
        raise requests.RequestException(message)
    adopt({**payload, "manager_url": manager_url, "session_token": token or session_token_for(manager_url)})
    return message + (f" ⚠️ {body['warning']}" if body.get("warning") else "")


def register_until_accepted(config: dict, agent_url: str) -> threading.Thread:
    """registers in the background, asking again while the manager does not answer (started after
    the agent, or restarting)"""

    def keep_trying():
        said = False
        while True:
            try:
                message = register(config, agent_url)
                logm.console.log(f"✅ registered with {config['manager_url']}: {message}")
                if not pybagent.accept_launch:
                    logm.console.log(f"its run is launched from its form: {agent_url}/session/agent/registration/waiting")
                return
            except Refused as refusal:
                logm.console.log(f"❌ the manager {config['manager_url']} refused the registration of "
                                 f"{config['agent_name']}: {refusal}")
                return
            except (requests.RequestException, ValueError) as error:
                # said once: the agent asks again every few seconds
                if not said:
                    logm.console.log(f"⏳ the manager {config['manager_url']} does not answer ({type(error).__name__}): "
                                     f"registering again every {RETRY_S} s")
                    said = True
            time.sleep(RETRY_S)

    thread = threading.Thread(target=keep_trying, name="registration", daemon=True)
    thread.start()
    return thread
