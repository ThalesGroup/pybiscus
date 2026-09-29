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
registered_agents_meta = {}   # name -> {geo_location, bouquet, location, organisation, role, agent_url}
manager_port = None
session_is_running = False
agent_gui_json_presets = None
session_client_id_counter = -1
# clients registered when the session was launched: their rank is their cid and partition_id, stable
# whatever the number of polls of their waiting page
session_clients = []
late_client_cids = {}         # name -> cid of the clients registered after the launch

def clear_session():
    global registered_clients
    registered_clients = {}
    global registered_servers
    registered_servers = {}
    global registered_agents_meta
    registered_agents_meta = {}
    # NB: manager_port n'est PAS réinitialisé ici : c'est un paramètre de lancement
    # (fixé dans main()), pas un état de session. Le remettre à None cassait les URLs
    # du template manager (http://localhost:None/...).
    global session_is_running
    session_is_running = False
    global agent_gui_json_presets
    agent_gui_json_presets = None
    global session_client_id_counter
    session_client_id_counter = -1
    global session_clients
    session_clients = []
    global late_client_cids
    late_client_cids = {}

def generate_new_cid():
    global session_client_id_counter
    session_client_id_counter += 1
    return str(session_client_id_counter)

# **************************

def main():

    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=5555, help="Port to run the manager on")
    # agents on other hosts send it their registration and logs: they need 0.0.0.0 (or an address)
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Listening address (default: 127.0.0.1; 0.0.0.0 when agents run on other hosts, or in a container)",
    )
    args = parser.parse_args()

    global manager_port
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}")
    pybiscus_manager_app.run(host=args.host, port=manager_port)

# **************************

if __name__ == "__main__":
    main()
