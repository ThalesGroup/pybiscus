from flask import jsonify, request

from pybiscus.session.agent import ui_settings
from pybiscus.session.agent.pybiscus_agent import rest_server

# ..........................................................
# .... GET /ui/settings ....................................
# ..........................................................

@rest_server.route("/ui/settings", methods=["GET"])
def get_ui_settings():
    return jsonify(ui_settings.state())

# ..........................................................
# .... PATCH /ui/settings ..................................
# ..........................................................
# body: {"scope": "agent" | "machine", "values": {name: value | null}}
# ..........................................................

@rest_server.route("/ui/settings", methods=["PATCH"])
def patch_ui_settings():
    body = request.get_json(silent=True) or {}
    values = body.get("values")
    if not isinstance(values, dict):
        return jsonify({"error": "a 'values' object is required"}), 400
    try:
        return jsonify(ui_settings.update(body.get("scope"), values))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

# ..........................................................
# .... DELETE /ui/settings?scope=agent|machine .............
# ..........................................................

@rest_server.route("/ui/settings", methods=["DELETE"])
def reset_ui_settings():
    try:
        return jsonify(ui_settings.reset(request.args.get("scope")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
