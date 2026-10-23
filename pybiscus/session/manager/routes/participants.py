from flask import jsonify, render_template, request

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.session import invitations
from pybiscus.session.manager.routes.sites import _invitation_problem
from pybiscus.session.manager.session_manager import pybiscus_manager_app

# The agents of this manager's session as its operator manages them: the invitations it issued,
# the agents registered with them or with the session token, the registrations refused.
# Administration token only: the participants hold the session token or their invitation's.


def _registered() -> dict:
    return {**{name: "client" for name in sm.registered_clients}, **{name: "server" for name in sm.registered_servers}}


@pybiscus_manager_app.route("/pybiscus-session/participants", methods=["GET"])
def pybiscus_manager_participants_page():
    return render_template("pybiscus/participants.html", bouquet=sm.bouquet,
                           participant_states=invitations.participant_state_protocol(),
                           default_days=invitations.DEFAULT_DAYS, soon_days=invitations.SOON_DAYS,
                           roles=list(invitations.AGENT_ROLES))


@pybiscus_manager_app.route("/pybiscus-session/participants.json", methods=["GET"])
def pybiscus_manager_participants():
    registered = _registered()
    rows = invitations.participants(sm.manager_port, registered, sm.refused_agents)
    for row in rows:
        meta = sm.registered_agents_meta.get(row["name"]) or {}
        row.update({key: meta.get(key) for key in ("organisation", "location") if meta.get(key)})
        if row["name"] in registered:
            row["agent_state"] = sm.agent_states.get(row["name"])
    return jsonify({"require_agent_invitation": sm.require_agent_invitation, "invitation_problem": _invitation_problem(),
                    "bouquet": sm.bouquet, "url": sm.manager_url, "participants": rows})


@pybiscus_manager_app.route("/pybiscus-session/participants/invite", methods=["POST"])
def pybiscus_manager_invite_agent():
    """the invitation's file, given once: only its token's digest is kept"""
    data = request.get_json(silent=True) or {}
    problem = _invitation_problem()
    if problem:
        return jsonify({"status": "error", "message": problem}), 409
    name, role, days = data.get("name"), data.get("role", "client"), data.get("days", invitations.DEFAULT_DAYS)
    try:
        days = int(days)
        invitation, path = invitations.issue_agent(sm.manager_port, name, role, days)
    except (TypeError, ValueError) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    sm.refused_agents.pop(name, None)
    logm.console.log(f"🎫 invitation of the agent {name} ({role}) issued, until {invitation.expires:%Y-%m-%d} ({path})")
    return jsonify({"status": "ok", "file_name": path.name, "path": str(path), "content": invitations.invitation_text(invitation)})


@pybiscus_manager_app.route("/pybiscus-session/participants/revoke", methods=["POST"])
def pybiscus_manager_revoke_agent():
    name = (request.get_json(silent=True) or {}).get("name")
    try:
        invitations.revoke(sm.manager_port, name, "agents")
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    logm.console.log(f"✗ invitation of the agent {name} revoked")
    return jsonify({"status": "ok"})


@pybiscus_manager_app.route("/pybiscus-session/participants/forget", methods=["POST"])
def pybiscus_manager_forget_agent():
    """a revoked or expired invitation, or a refused registration, out of the list"""
    name = (request.get_json(silent=True) or {}).get("name")
    entry = invitations.load_registry(sm.manager_port)["agents"].get(name)
    # an active invitation stays: only its refused attempt is cleared
    if entry is not None and not invitations.active(entry):
        invitations.forget(sm.manager_port, name, "agents")
    sm.refused_agents.pop(name, None)
    return jsonify({"status": "ok"})
