import argparse
from flask import Flask, render_template, request, jsonify, render_template_string
import requests

app = Flask(__name__)

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
                    # "registered_clients": list(registered_clients.keys())
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                    # "registered_clients": list(registered_clients.keys())
                })

        registered_clients[name] = client_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
            "server" : server_url,
            # "registered_clients": list(registered_clients.keys())
        })
    else:
        return jsonify({"status": "error", "message": "Missing 'name' or 'client_url'"}), 400

@app.route("/clients", methods=["GET"])
def list_clients():
    return jsonify({"clients": registered_clients})

# sub-view URL
# visualize a graph of session participants
@app.route("/visualize")
def visualize():
    return render_template("visualize.html", server_url=server_url)

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

# **********************
# *** Log management ***
# **********************

from threading import Lock

log_messages = []  # Liste pour stocker les messages
log_lock = Lock()  # Verrou pour gérer l'accès concurrent aux messages

@app.route('/webhook/logs', methods=['POST'])
def receive_log():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # Verrouiller l'accès pour éviter les problèmes de concurrence
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

    # Retourner les messages stockés sous forme de JSON
    return jsonify(_log_messages)

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
