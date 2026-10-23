import hmac
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


def vouches_for(name, role, token) -> Optional[str]:
    """why this manager does not vouch for the token as the one of this agent, None when it does
    (a server's agent checking the run config a client posts to it)"""
    if not isinstance(token, str) or not token:
        return "no token"
    invited = invitations.invited_agent(sm.manager_port, token)
    if invited is not None:
        if invited["name"] != name or invited["role"] != role:
            return f"the token is the invitation of {invited['name']} ({invited['role']}), not of {name} ({role})"
        return None
    if sm.session_token and hmac.compare_digest(token.encode(), sm.session_token.encode()):
        if invitations.reserved_agent(sm.manager_port, name):
            return f"{name} is an invited agent: its invitation's token is required"
        if sm.require_agent_invitation:
            return "this manager requires an invitation of its agents"
        return None
    return invitations.agent_invitation_problem(sm.manager_port, token) or "not a token of this session"
