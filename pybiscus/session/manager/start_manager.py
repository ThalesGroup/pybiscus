import argparse
from flask import Flask, render_template, request, jsonify, render_template_string
import requests
from flask_cors import CORS
from threading import Lock

app = Flask(__name__)
CORS(app, origins="*")

# global variable that contains the application context
registered_clients = {}
server_url = None
manager_port = None

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    client_url = data.get("client_url")

    if name and client_url:

        if name in registered_clients:
            
            if registered_clients[name] == client_url:
                return jsonify({
                    "status": "success",
                    "message": f"Client '{name}' already registered.",
                    "server" : server_url,
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                })

        registered_clients[name] = client_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
            "server" : server_url,
        })
    else:
        return jsonify({"status": "error", "message": "Missing 'name' or 'client_url'"}), 400

@app.route("/clients", methods=["GET"])
def list_clients():
    return jsonify({"clients": registered_clients})

@app.route("/clients", methods=["DELETE"])
def revoke_clients():
    global registered_clients
    registered_clients = {}

    return jsonify({"status": "success"}), 200

# sub-view URL
# visualize a graph of session participants
@app.route("/visualize")
def visualize():
    return render_template("visualize.html", server_url=server_url)

# sub-view URL
# visualize logs and metrics
@app.route("/show_run")
def show_run():
    return render_template("show_run.html", server_url=server_url)

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@app.route("/manage")
def manage():
    return render_template("manager.html", server_url=server_url)

@app.route("/ping-server")
def ping_server():
    try:
        res = requests.get(server_url)
        return jsonify({"message": res.text})
    except Exception as e:
        return jsonify({"message": f"Error contacting server: {e}"}), 500

# ************************
# *** Agent management ***
# ************************

agent_messages = []  # stored messages list
agent_lock = Lock()  # lock used to prevent agent logs concurrent access

@app.route('/webhook/agents', methods=['POST'])
def receive_agents():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # private section
    with agent_lock:
        global agent_messages
        agent_messages.append({'source': source, 'message': message})

    return jsonify({"status": "success"}), 200

@app.route('/agents', methods=['GET'])
def get_agents():

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

@app.route('/webhook/logs', methods=['POST'])
def receive_log():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # private section
    with log_lock:
        global log_messages
        log_messages.append({'source': source, 'message': message})

    return jsonify({"status": "success"}), 200

@app.route('/logs', methods=['GET'])
def get_logs():

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

@app.route('/webhook/metrics', methods=['POST'])
def receive_metrics():
    data = request.json
    metrics = data.get('metrics', '')
    source = data.get('source', 'unknown')
    log = { 'source' : source, 'message' : str(metrics) }

    # private section
    with metrics_lock:
        global metrics_messages
        metrics_messages.append(log)

    return jsonify({"status": "success"}), 200

@app.route('/metrics', methods=['GET'])
def get_metricss():

    with metrics_lock:
        global metrics_messages
        _metrics_messages = metrics_messages
        metrics_messages = []

    # return json encoded messages
    return jsonify(_metrics_messages)

# **************************

def main():
    global server_url
    global manager_port

    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=6000, help="Port to run the manager on")
    parser.add_argument("--server-url", type=str, required=True, help="URL of the central server (e.g. http://localhost:5555)")
    args = parser.parse_args()

    server_url = args.server_url
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}, connected to server: {server_url}")
    app.run(port=manager_port)

if __name__ == "__main__":
    main()
