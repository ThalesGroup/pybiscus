import argparse
from flask import Flask
from flask_cors import CORS

from pybiscus.session.csrf import HEADER, require_pybiscus_header

# **************************

pybiscus_manager_app = Flask(__name__)
require_pybiscus_header(pybiscus_manager_app)

# the agents' pages call the manager from their own origin (registration, waiting for the session):
# the local ones are always allowed, those of other hosts through --allow-origin. The former "*"
# let any site open in the operator's browser read the manager and drive it
LOCAL_ORIGINS = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

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
registered_clients_cpu = {}   # name -> {machine, cpu_cores}, sent by the agent at registration

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
    global registered_clients_cpu
    registered_clients_cpu = {}

def client_threads(name):
    """the physical cores of the client's machine shared between the session's clients on it, or
    None when the agent did not say (former agent pages)"""

    info = registered_clients_cpu.get(name) or {}
    machine, cores = info.get("machine"), info.get("cpu_cores")
    if not machine or not isinstance(cores, int) or cores < 1:
        return None
    on_machine = [c for c in session_clients if (registered_clients_cpu.get(c) or {}).get("machine") == machine]
    return max(1, cores // max(1, len(on_machine)))

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
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        help="origin of agent pages on another host, e.g. http://agenthost:5001 (repeatable; local origins are always allowed)",
    )
    args = parser.parse_args()

    CORS(pybiscus_manager_app, origins=[LOCAL_ORIGINS, *args.allow_origin], allow_headers=["Content-Type", HEADER])

    global manager_port
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}")
    pybiscus_manager_app.run(host=args.host, port=manager_port)

# **************************

if __name__ == "__main__":
    main()
