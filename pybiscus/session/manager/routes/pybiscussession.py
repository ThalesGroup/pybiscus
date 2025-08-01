from flask import render_template, request, jsonify
import requests
from threading import Lock
import pybiscus.session.manager.session_manager
from pybiscus.session.manager.session_manager import pybiscus_manager_app

# **************************

@pybiscus_manager_app.route("/pybiscus-session/run", methods=["GET"])
def pybiscus_manager_run_session():

    pybiscus.session.manager.session_manager.session_is_running = True

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agent", methods=["POST"])
def pybiscus_manager_register_agent():

    data = request.json

    name = data.get("name")

    if name is None:
        return jsonify({"status": "error", "message": "Missing 'name'"}), 400

    agent_url = data.get("agent_url")

    if agent_url is None:
        return jsonify({"status": "error", "message": "Missing 'agent_url'"}), 400

    role = data.get("role")

    if role is None:
        return jsonify({"status": "error", "message": "Missing 'role'"}), 400

    if role == "server":

        if name in pybiscus.session.manager.session_manager.registered_servers:
            
            if pybiscus.session.manager.session_manager.registered_servers[name] == agent_url:
                return jsonify({
                    "status": "success",
                    "message": f"Server '{name}' already registered.",
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Server '{name}' already registered with a different URL.",
                }), 400

        pybiscus.session.manager.session_manager.registered_servers[name] = agent_url

        return jsonify({
            "status": "success",
            "message": f"Server '{name}' registered.",
        })

    if role == "client":

        if name in pybiscus.session.manager.session_manager.registered_clients:
            
            if pybiscus.session.manager.session_manager.registered_clients[name] == agent_url:
                return jsonify({
                    "status": "success",
                    "message": f"Client '{name}' already registered.",
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                }), 400

        pybiscus.session.manager.session_manager.registered_clients[name] = agent_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
        })

    else:
        return jsonify({"status": "error", "message": f"Bad role={role}, it should be server or client"}), 400

# **************************

@pybiscus_manager_app.route("/pybiscus-session/params", methods=["GET"])
def pybiscus_manager_get_session_params():

    if not pybiscus.session.manager.session_manager.session_is_running:
        return jsonify({"status": "error", "message": "session is not running yet"})

    first_item = next(iter(pybiscus.session.manager.session_manager.registered_servers.items()))
    _, first_item_value = first_item

    return jsonify({
        "status" : "success",
        "message": "session is running",
        "server" : first_item_value,
    })

    #TODO: check return value
    
    data = request.json

    name = data.get("name")

    if name is None:
        return jsonify({"status": "error", "message": "Missing 'name'"}), 400

    agent_url = data.get("agent_url")

    if agent_url is None:
        return jsonify({"status": "error", "message": "Missing 'agent_url'"}), 400

    role = data.get("role")

    if role is None:
        return jsonify({"status": "error", "message": "Missing 'role'"}), 400

    if role == "server":

        if name in pybiscus.session.manager.session_manager.registered_servers:
            
            if pybiscus.session.manager.session_manager.registered_servers[name] == agent_url:
                return jsonify({
                    "status": "success",
                    "message": "session is running",
                    "role"   : role,
                    "server" : pybiscus.session.manager.session_manager.server_url,
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Server '{name}' already registered with a different URL.",
                }), 400

        return jsonify({
            "status": "error",
            "message": f"Server '{name}' not registered.",
        }), 400

    if role == "client":

        if name in pybiscus.session.manager.session_manager.registered_clients:
            
            if pybiscus.session.manager.session_manager.registered_clients[name] == agent_url:
                return jsonify({
                    "status": "success",
                    "message": "session is running",
                    "role"   : role,
                    "server" : pybiscus.session.manager.session_manager.server_url,
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                }), 400

        return jsonify({
            "status": "error",
            "message": f"Client '{name}' not registered.",
        }), 400

    else:
        return jsonify({"status": "error", "message": f"Bad role={role}, it should be server or client"}), 400

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agents", methods=["GET"])
def pybiscus_manager_list_clients():
    return jsonify({
        "clients": pybiscus.session.manager.session_manager.registered_clients,
        "servers": pybiscus.session.manager.session_manager.registered_servers,
    })

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agents", methods=["DELETE"])
def pybiscus_manager_revoke_clients():
    pybiscus.session.manager.session_manager.registered_servers = {}
    pybiscus.session.manager.session_manager.registered_clients = {}

    return jsonify({"status": "success"}), 200

# **************************

# sub-view URL
# show session participant agents graph and logs
@pybiscus_manager_app.route("/pybiscus-session/show_agents")
def pybiscus_manager_show_agents():
    return render_template("show_agents.html", manager_port=pybiscus.session.manager.session_manager.manager_port)

# **************************

# sub-view URL
# show logs and metrics
@pybiscus_manager_app.route("/pybiscus-session/show_run")
def pybiscus_manager_show_run():
    return render_template("show_run.html", manager_port=pybiscus.session.manager.session_manager.manager_port)

# **************************

@pybiscus_manager_app.route("/pybiscus-session/show_blank")
def pybiscus_manager_show_blank():
    return render_template("show_blank.html")

# **************************

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@pybiscus_manager_app.route("/pybiscus-session/manage")
def pybiscus_manager_manage():
    return render_template("manager.html")

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

@pybiscus_manager_app.route('/pybiscus-session/agents_logs', methods=['GET'])
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
