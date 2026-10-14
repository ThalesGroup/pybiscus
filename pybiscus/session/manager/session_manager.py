import argparse
import os
import socket
from threading import Lock
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
# the bouquet this manager's session belongs to (--bouquet): the one its page shows, whatever the
# agents declare at their registration; None keeps showing theirs
bouquet = None
bouquet_color = None   # --color: a CSS colour; None derives one from the bouquet's name
# --bouquet-mismatch: an agent declaring another bouquet than --bouquet is refused, or only warned
# about: it has most likely registered with the wrong manager
bouquet_mismatch = "refuse"
manager_url = None     # how the other managers reach this one's page
# where this manager is (--location, --geo), drawn on the maps of a hierarchical session
manager_location = None
manager_geo = None     # {"type": "coordinates", "latitude", "longitude"}
# last state each agent declared (AgentState): the page keeps its own from the agents' log, this one
# is what the upper-level manager is told
agent_states = {}
# bouquet -> {"topology": what its manager reported, "last_seen": time}, for the lower levels whose
# manager was started with --upper-url pointing to this one
lower_levels = {}
lower_levels_lock = Lock()
# with --upper-url: {"url", "bouquet", "color", "reached", "problem", "last_contact", "session"}, shown
# in the page; "session" is the upper level's: {"running", "constraints"}
upper_link = None
# the choices of the running session that its lower levels must keep: {"model": label, "data": label}
session_constraints = None
# lower-level bouquet -> the client of this session that relays it, designated in this manager's page
relays = {}
# the relays when the session was launched: Flower clients, but without data nor computation
session_relays = []
# lower-level bouquet -> the link its relay and its server share (ConfigSessionLink), made at launch
session_links = {}
# with --upper-url: the link to the upper level the session was launched with
upper_session_link = None
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
    global agent_states
    agent_states = {}
    global session_constraints
    session_constraints = None
    global relays
    relays = {}
    global session_relays
    session_relays = []
    global session_links
    session_links = {}
    global upper_session_link
    upper_session_link = None

def client_threads(name):
    """the physical cores of the client's machine shared between the session's clients on it, or
    None when the agent did not say (former agent pages)"""

    info = registered_clients_cpu.get(name) or {}
    machine, cores = info.get("machine"), info.get("cpu_cores")
    if not machine or not isinstance(cores, int) or cores < 1:
        return None
    on_machine = [c for c in session_clients if (registered_clients_cpu.get(c) or {}).get("machine") == machine]
    return max(1, cores // max(1, len(on_machine)))

def proposed_flower_port():
    """the Flower server port proposed in the session form, one per manager port (5555 -> 3333,
    5556 -> 3334): two sessions on one machine left at 3333 shared their clients"""
    port = 3333 + (manager_port - 5555)
    return port if 1024 <= port <= 65535 else 3333

def generate_new_cid():
    global session_client_id_counter
    session_client_id_counter += 1
    return str(session_client_id_counter)

# **************************

def geo_coordinates(text: str) -> dict:
    """"LAT,LON" as an agent's registration gives its coordinates"""
    try:
        latitude, longitude = (float(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected LAT,LON in degrees, e.g. 48.714,2.203: {text!r}")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise argparse.ArgumentTypeError(f"latitude in [-90, 90], longitude in [-180, 180]: {text!r}")
    return {"type": "coordinates", "latitude": latitude, "longitude": longitude}

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
    parser.add_argument("--bouquet", default=None,
                        help="bouquet of this manager's session, shown in its page (default: the bouquets the agents declare)")
    parser.add_argument("--bouquet-mismatch", choices=("refuse", "warn"), default="refuse",
                        help="an agent declaring another bouquet than --bouquet: refused (default), or registered with a warning")
    parser.add_argument("--color", default=None,
                        help="CSS colour of this manager's page (default: derived from --bouquet, the same for the same name)")
    parser.add_argument("--location", default=None, help="where this manager is, e.g. palaiseau-dc (shown on the maps)")
    parser.add_argument("--geo", type=geo_coordinates, default=None,
                        help="this manager's coordinates, LAT,LON (default on the maps: next to its session's server)")
    parser.add_argument("--upper-url", default=None,
                        help="URL of the upper-level manager of a hierarchical session, e.g. http://localhost:5555: "
                             "this manager reports its bouquet's topology to it (requires --bouquet)")
    parser.add_argument("--upper-token", default=None,
                        help="session token of the upper-level manager (default: $PYBISCUS_UPPER_TOKEN, else its token file "
                             "when it runs on this machine, started from the same directory)")
    parser.add_argument("--require-token", action="store_true",
                        help="require the tokens on the loopback too (always required when listening beyond it)")
    args = parser.parse_args()
    if args.upper_url and not args.bouquet:
        parser.error("--upper-url requires --bouquet: the upper-level manager tells its lower levels apart by their bouquet")

    CORS(pybiscus_manager_app, origins=[LOCAL_ORIGINS, *args.allow_origin], allow_headers=["Content-Type", "Authorization", HEADER])

    global manager_port, admin_token, session_token, tokens_are_required, bouquet, bouquet_color, bouquet_mismatch, manager_url, manager_location, manager_geo
    manager_port=args.port
    manager_location, manager_geo = args.location, args.geo
    bouquet = args.bouquet
    bouquet_color = args.color
    bouquet_mismatch = args.bouquet_mismatch
    tokens_are_required = tokens_required(args.host, args.require_token)
    admin_name, session_name = manager_token_names(manager_port)
    admin_token = component_token(admin_name, args.admin_token) if tokens_are_required else None
    session_token = component_token(session_name, args.session_token)

    print(f"🚀 Manager starting on port {manager_port}" + (f", bouquet {bouquet}" if bouquet else ""))
    browsed_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    # listening on every interface, the other managers are elsewhere: they need the machine's name
    linked_host = socket.getfqdn() if args.host in ("0.0.0.0", "::") else browsed_host
    manager_url = f"http://{linked_host}:{manager_port}"
    print_access("manager", f"http://{browsed_host}:{manager_port}/pybiscus-session/manage", admin_token)
    print(f"🔑 session token, for the agents (shown in the manager page too): {session_token}", flush=True)
    if args.upper_url:
        from pybiscus.session.manager.upper_level import report_to_upper_level
        report_to_upper_level(args.upper_url, args.upper_token)
    pybiscus_manager_app.run(host=args.host, port=manager_port)

# **************************

if __name__ == "__main__":
    main()
