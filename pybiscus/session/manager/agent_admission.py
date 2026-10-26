import time
from typing import Optional

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.session import invitations
from pybiscus.session.auth import invited_agent

MAX_REFUSED = 50


def agent_problem(name: Optional[str], role: Optional[str] = None) -> Optional[str]:
    """why the request may not act as this agent, None when it may: an invitation's token acts
    as its own agent only, an invited name is not taken with the session token"""
    invited = invited_agent()
    if invited is not None:
        if name != invited["name"]:
            return f"the invitation of {invited['name']} is not one of {name}"
        if role is not None and role != invited["role"]:
            return f"{name} is invited as {invited['role']}, not as {role}"
        return None
    reserved = invitations.reserved_agent(sm.manager_port, name) if name else None
    if reserved:
        return f"{name} is an invited agent: its invitation's token is required"
    if sm.require_agent_invitation:
        return "this manager requires an invitation of its agents (session_manager invite --agent)"
    return None


def feed_problem() -> Optional[str]:
    """why a run may not post to the page's feeds (logs, metrics, vignettes), None when it may"""
    if invited_agent() is None and sm.require_agent_invitation:
        return "this manager requires an invitation of its agents: their runs post with it"
    return None


def refuse_agent(name, role, reason: str) -> None:
    """kept for the participants page: someone took an invited name, or came without an invitation"""
    if not isinstance(name, str) or not name:
        return
    sm.refused_agents.pop(name, None)
    sm.refused_agents[name] = {"time": time.time(), "reason": reason, "role": role if isinstance(role, str) else None}
    while len(sm.refused_agents) > MAX_REFUSED:
        sm.refused_agents.pop(next(iter(sm.refused_agents)))
    logm.console.log(f"⛔ registration of {name} refused: {reason}")
