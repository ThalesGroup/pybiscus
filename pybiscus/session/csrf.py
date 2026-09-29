from flask import Flask, jsonify, request

# A page of another site open in the operator's browser could drive the agents and the manager,
# even on 127.0.0.1: browsers send "simple" cross-site requests (a GET, a form, a multipart
# upload built in JavaScript) without asking. Every request that changes something must carry
# this header: a cross-site page cannot add it without a CORS preflight, which the agents refuse
# (no CORS) and the manager grants to its allowed origins only. Pybiscus' own pages and the calls
# between its components add it. Not an authentication: anyone on the network can send it.
HEADER = "X-Pybiscus"

_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def require_pybiscus_header(app: Flask) -> None:

    @app.before_request
    def _check_pybiscus_header():
        if request.method in _SAFE_METHODS or request.headers.get(HEADER):
            return None
        return jsonify({"error": f"missing {HEADER} header: requests that change something must carry it"}), 403
