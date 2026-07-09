import argparse
from flask import Flask
from flask_cors import CORS

# **************************

pybiscus_manager_app = Flask(__name__)
CORS(pybiscus_manager_app, origins="*")

# **************************

# global variable that contains the application context
registered_clients = {}
registered_servers = {}
manager_port = None
session_is_running = False
agent_gui_json_presets = None
session_client_id_counter = -1

def clear_session():
    global registered_clients
    registered_clients = {}
    global registered_servers
    registered_servers = {}
    # NB: manager_port n'est PAS réinitialisé ici : c'est un paramètre de lancement
    # (fixé dans main()), pas un état de session. Le remettre à None cassait les URLs
    # du template manager (http://localhost:None/...).
    global session_is_running
    session_is_running = False
    global agent_gui_json_presets
    agent_gui_json_presets = None
    global session_client_id_counter
    session_client_id_counter = -1

def generate_new_cid():
    global session_client_id_counter
    session_client_id_counter += 1
    return str(session_client_id_counter)

# **************************

def main():

    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=5555, help="Port to run the manager on")
    args = parser.parse_args()

    global manager_port
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}")
    pybiscus_manager_app.run(port=manager_port)

# **************************

if __name__ == "__main__":
    main()
