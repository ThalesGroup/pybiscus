import threading
import time

import requests
from flask import Response, jsonify, request

import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.manager.session_manager as sm
from pybiscus.flower.sessionlink import LINK_HEADER, MAX_WAIT_S
from pybiscus.session.auth import session_access
from pybiscus.session.manager.session_manager import pybiscus_manager_app

# The mailbox of the links between the levels of a hierarchical session (transport "manager"). A
# manager keeps the objects of the links it made for its lower levels, which its relays and,
# through their own managers, the lower levels' servers put and take. The link it received from its
# upper level is relayed there: each end only talks to its own manager, with its own session's
# token, and the traffic goes from the lower levels up, the way they already reach their parent.

KINDS = ("model", "aggregate")

# (link_id, kind, round) -> (arrays as an npz, header as json)
_mailbox = {}
_arrived = threading.Condition()


def _own(link_id: str) -> bool:
    return any(link.get("link_id") == link_id for link in sm.session_links.values())


def _upper(link_id: str) -> bool:
    return bool(sm.upper_session_link) and sm.upper_session_link.get("link_id") == link_id


def _forget_other_links() -> None:
    """the objects of the links of an earlier session: never taken now"""
    for key in [key for key in _mailbox if not _own(key[0])]:
        del _mailbox[key]


def _relay_up(method: str, timeout: float) -> Response:
    from pybiscus.session.manager.upper_level import _headers
    upper = sm.upper_link["url"]
    headers = _headers(upper, sm.upper_token)
    if LINK_HEADER in request.headers:
        headers[LINK_HEADER] = request.headers[LINK_HEADER]
    try:
        answer = requests.request(method, upper + request.full_path.rstrip("?"), data=request.get_data() or None,
                                  headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"the upper level's manager is out of reach: {type(e).__name__}"}), 503
    response = Response(answer.content, status=answer.status_code, content_type=answer.headers.get("Content-Type"))
    if LINK_HEADER in answer.headers:
        response.headers[LINK_HEADER] = answer.headers[LINK_HEADER]
    return response


def _unknown(link_id: str):
    return jsonify({"status": "error", "message": f"no running session of this manager has the link {link_id}"}), 404


@pybiscus_manager_app.route("/pybiscus-session/link/<link_id>/<kind>/<int:server_round>", methods=["PUT"])
@session_access
def link_put(link_id, kind, server_round):
    if kind not in KINDS:
        return jsonify({"status": "error", "message": f"kind {kind}: {' or '.join(KINDS)} expected"}), 400
    if not _own(link_id):
        return _relay_up("PUT", 60) if _upper(link_id) else _unknown(link_id)
    with _arrived:
        _forget_other_links()
        _mailbox[(link_id, kind, server_round)] = (request.get_data(), request.headers.get(LINK_HEADER, "{}"))
        _arrived.notify_all()
    logm.console.log(f"📬 link {link_id}: {kind} of round {server_round} in the mailbox ({len(request.get_data()) // 1024} kB)")
    return jsonify({"status": "ok"})


@pybiscus_manager_app.route("/pybiscus-session/link/<link_id>/<kind>/<int:server_round>", methods=["GET"])
@session_access
def link_get(link_id, kind, server_round):
    """the object, taken out of the mailbox; 204 when it has not come within `wait` seconds"""
    if kind not in KINDS:
        return jsonify({"status": "error", "message": f"kind {kind}: {' or '.join(KINDS)} expected"}), 400
    wait = min(max(request.args.get("wait", 0, type=float), 0), MAX_WAIT_S)
    if not _own(link_id):
        return _relay_up("GET", wait + 30) if _upper(link_id) else _unknown(link_id)
    deadline = time.monotonic() + wait
    with _arrived:
        while (link_id, kind, server_round) not in _mailbox:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return Response(status=204)
            _arrived.wait(remaining)
        arrays, header = _mailbox.pop((link_id, kind, server_round))
    response = Response(arrays, content_type="application/octet-stream")
    response.headers[LINK_HEADER] = header
    return response


@pybiscus_manager_app.route("/pybiscus-session/link/<link_id>", methods=["DELETE"])
@session_access
def link_reset(link_id):
    """called by the relay before its first round: the upper level starts each exchange"""
    if not _own(link_id):
        return _relay_up("DELETE", 10) if _upper(link_id) else _unknown(link_id)
    with _arrived:
        for key in [key for key in _mailbox if key[0] == link_id]:
            del _mailbox[key]
    return jsonify({"status": "ok"})
