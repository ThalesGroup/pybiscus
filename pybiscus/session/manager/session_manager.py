import argparse
import os
from flask import Flask
from flask_cors import CORS

from pybiscus.session.auth import SESSION_TOKEN_ENV, component_token, manager_token_names, print_access, require_tokens, tokens_required
from pybiscus.session.csrf import HEADER, require_pybiscus_header

# **************************

pybiscus_manager_app = Flask(__name__)
require_pybiscus_header(pybiscus_manager_app)

admin_token = None     # the operator's: the manager's pages and actions
# the participants': registration, session parameters, webhooks. Created even when the manager
# requires none: an agent listening on the network requires it from the others
session_token = None
tokens_are_required = False

require_tokens(pybiscus_manager_app, "manager",
               enabled=lambda: tokens_are_required,
               cookie=lambda: f"pybiscus-manager-{manager_port}",
               access_token=lambda: admin_token,
               session_token=lambda: session_token)

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
    parser.add_argument("--admin-token", default=os.environ.get("PYBISCUS_MANAGER_TOKEN"),
                        help="token of the manager's pages (default: $PYBISCUS_MANAGER_TOKEN, else the one of the previous start, else a new one)")
    parser.add_argument("--session-token", default=os.environ.get(SESSION_TOKEN_ENV),
                        help=f"token given to the agents (default: ${SESSION_TOKEN_ENV}, else the one of the previous start, else a new one)")
    parser.add_argument("--require-token", action="store_true",
                        help="require the tokens on the loopback too (always required when listening beyond it)")
    args = parser.parse_args()

    CORS(pybiscus_manager_app, origins=[LOCAL_ORIGINS, *args.allow_origin], allow_headers=["Content-Type", "Authorization", HEADER])

    global manager_port, admin_token, session_token, tokens_are_required
    manager_port=args.port
    tokens_are_required = tokens_required(args.host, args.require_token)
    admin_name, session_name = manager_token_names(manager_port)
    admin_token = component_token(admin_name, args.admin_token) if tokens_are_required else None
    session_token = component_token(session_name, args.session_token)

    print(f"🚀 Manager starting on port {manager_port}")
    browsed_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print_access("manager", f"http://{browsed_host}:{manager_port}/pybiscus-session/manage", admin_token)
    print(f"🔑 session token, for the agents (shown in the manager page too): {session_token}", flush=True)
    pybiscus_manager_app.run(host=args.host, port=manager_port)

# **************************

if __name__ == "__main__":
    main()
