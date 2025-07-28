from flask import render_template, request, jsonify
import requests
from threading import Lock
import pybiscus.session.manager.session_manager
from pybiscus.session.manager.session_manager import pybiscus_manager_app

# **************************

@pybiscus_manager_app.route("/pybiscus-session/client", methods=["POST"])
def pybiscus_manager_register_client():

    data = request.json

    name       = data.get("name")
    client_url = data.get("client_url")

    if name and client_url:

        if name in pybiscus.session.manager.session_manager.registered_clients:
            
            if pybiscus.session.manager.session_manager.registered_clients[name] == client_url:
                return jsonify({
                    "status": "success",
                    "message": f"Client '{name}' already registered.",
                    "server" : pybiscus.session.manager.session_manager.server_url,
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                })

        pybiscus.session.manager.session_manager.registered_clients[name] = client_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
            "server" : pybiscus.session.manager.session_manager.server_url,
        })
    else:
        return jsonify({"status": "error", "message": "Missing 'name' or 'client_url'"}), 400

# **************************

@pybiscus_manager_app.route("/pybiscus-session/clients", methods=["GET"])
def pybiscus_manager_list_clients():
    return jsonify({"clients": pybiscus.session.manager.session_manager.registered_clients})

# **************************

@pybiscus_manager_app.route("/pybiscus-session/clients", methods=["DELETE"])
def pybiscus_manager_revoke_clients():
    pybiscus.session.manager.session_manager.registered_clients = {}

    return jsonify({"status": "success"}), 200

# **************************

# sub-view URL
# visualize a graph of session participants
@pybiscus_manager_app.route("/pybiscus-session/visualize")
def pybiscus_manager_visualize():
    return render_template("visualize.html", server_url=pybiscus.session.manager.session_manager.server_url)

# **************************

# sub-view URL
# visualize logs and metrics
@pybiscus_manager_app.route("/pybiscus-session/show_run")
def pybiscus_manager_show_run():
    return render_template("show_run.html", manager_port=pybiscus.session.manager.session_manager.manager_port)

# **************************

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@pybiscus_manager_app.route("/pybiscus-session/manage")
def pybiscus_manager_manage():
    return render_template("manager.html", server_url=pybiscus.session.manager.session_manager.server_url)

# **************************

@pybiscus_manager_app.route("/pybiscus-session/ping-server")
def pybiscus_manager_ping_server():
    try:
        res = requests.get(pybiscus.session.manager.session_manager.server_url)
        return jsonify({"message": res.text})
    except Exception as e:
        return jsonify({"message": f"Error contacting server: {e}"}), 500

# ************************
# *** Agent management ***
# ************************

agent_messages = []  # stored messages list
agent_lock = Lock()  # lock used to prevent agent logs concurrent access

# **************************

@pybiscus_manager_app.route('/webhook/agents', methods=['POST'])
def pybiscus_manager_receive_agents():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # private section
    with agent_lock:
        agent_messages.append({'source': source, 'message': message})

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/agents', methods=['GET'])
def pybiscus_manager_get_agents():

    with agent_lock:
        global agent_messages
        _agent_messages = agent_messages
        agent_messages = []

    # return json encoded messages
    return jsonify(_agent_messages)

# *******************************
# *** Pybiscus Log management ***
# *******************************

log_messages = []  # stored messages list
log_lock = Lock()  # lock used to prevent logs concurrent access

# **************************

@pybiscus_manager_app.route('/webhook/logs', methods=['POST'])
def pybiscus_manager_receive_log():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # private section
    with log_lock:
        log_messages.append({'source': source, 'message': message})

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/logs', methods=['GET'])
def pybiscus_manager_get_logs():

    with log_lock:
        global log_messages
        _log_messages = log_messages
        log_messages = []

    # return json encoded messages
    return jsonify(_log_messages)

# ***********************************
# *** Pybiscus Metrics management ***
# ***********************************

metrics_messages = []  # stored metrics list
metrics_lock = Lock()  # lock used to prevent metrics concurrent access

# **************************

@pybiscus_manager_app.route('/webhook/metrics', methods=['POST'])
def pybiscus_manager_receive_metrics():
    data = request.json
    metrics = data.get('metrics', '')
    source = data.get('source', 'unknown')
    log = { 'source' : source, 'message' : str(metrics) }

    # private section
    with metrics_lock:
        metrics_messages.append(log)

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/metrics', methods=['GET'])
def pybiscus_manager_get_metrics():

    with metrics_lock:
        global metrics_messages
        _metrics_messages = metrics_messages
        metrics_messages = []

    # return json encoded messages
    return jsonify(_metrics_messages)
