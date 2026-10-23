from flask import jsonify, render_template, request

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.session import invitations
from pybiscus.session.manager.session_manager import pybiscus_manager_app

# The sites of a hierarchical session as the upper level's operator manages them: the invitations
# this manager issued, the lower levels present and the ones refused. Administration token only:
# the participants hold the session token.


def _reports() -> dict:
    from pybiscus.session.manager.upper_level import lower_levels, transport_of
    return {level["bouquet"]: {"stale": level["stale"], "invited": level["invited"], "transport": transport_of(level["bouquet"]),
                               "relay": sm.relays.get(level["bouquet"])}
            for level in lower_levels()}


def _invitation_problem():
    """why this manager cannot invite, None when it can"""
    if not sm.serves_https:
        return "this manager serves HTTP: the token would travel in clear at each contact (start it with --tls-cert / --tls-key)"
    return None


@pybiscus_manager_app.route("/pybiscus-session/sites", methods=["GET"])
def pybiscus_manager_sites_page():
    return render_template("pybiscus/sites.html", bouquet=sm.bouquet, site_states=invitations.site_state_protocol(),
                           default_days=invitations.DEFAULT_DAYS, soon_days=invitations.SOON_DAYS)


@pybiscus_manager_app.route("/pybiscus-session/sites.json", methods=["GET"])
def pybiscus_manager_sites():
    reports = _reports()
    rows = invitations.sites(sm.manager_port, reports, sm.refused_lower_levels)
    listed = {row["bouquet"] for row in rows}
    # present without an invitation: accepted with the session token, without --require-invitation
    rows += [{"bouquet": bouquet, "state": invitations.SiteState.ADMITTED.value, "stale": report["stale"]}
             for bouquet, report in sorted(reports.items())
             if bouquet not in listed]
    for row in rows:
        row.update({key: value for key, value in reports.get(row["bouquet"], {}).items() if key in ("transport", "relay")})
    return jsonify({"require_invitation": sm.require_invitation, "invitation_problem": _invitation_problem(),
                    "bouquet": sm.bouquet, "url": sm.manager_url, "sites": rows})


@pybiscus_manager_app.route("/pybiscus-session/sites/invite", methods=["POST"])
def pybiscus_manager_invite_site():
    """the invitation's file, given once: only its token's digest is kept"""
    data = request.get_json(silent=True) or {}
    problem = _invitation_problem()
    if problem:
        return jsonify({"status": "error", "message": problem}), 409
    bouquet, days = data.get("bouquet"), data.get("days", invitations.DEFAULT_DAYS)
    try:
        days = int(days)
        invitation, path = invitations.issue(sm.manager_port, bouquet, days)
    except (TypeError, ValueError) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    sm.refused_lower_levels.pop(bouquet, None)
    logm.console.log(f"📨 invitation of {bouquet} issued, until {invitation.expires:%Y-%m-%d} ({path})")
    return jsonify({"status": "ok", "file_name": path.name, "path": str(path), "content": invitations.invitation_text(invitation)})


@pybiscus_manager_app.route("/pybiscus-session/sites/revoke", methods=["POST"])
def pybiscus_manager_revoke_site():
    bouquet = (request.get_json(silent=True) or {}).get("bouquet")
    try:
        invitations.revoke(sm.manager_port, bouquet)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    logm.console.log(f"✗ invitation of {bouquet} revoked")
    return jsonify({"status": "ok"})


@pybiscus_manager_app.route("/pybiscus-session/sites/forget", methods=["POST"])
def pybiscus_manager_forget_site():
    """a revoked or expired invitation, or a refused site, out of the list"""
    bouquet = (request.get_json(silent=True) or {}).get("bouquet")
    entry = invitations.load_registry(sm.manager_port)["invitations"].get(bouquet)
    if invitations.active(entry):
        # an active site: only its refused attempt is cleared
        sm.refused_lower_levels.pop(bouquet, None)
        return jsonify({"status": "ok"})
    if entry is not None:
        invitations.forget(sm.manager_port, bouquet)
    sm.refused_lower_levels.pop(bouquet, None)
    return jsonify({"status": "ok"})
