import argparse
import atexit
import os
import socket
import sys
from threading import Lock
import pybiscus.session.theme
from flask import Flask
from flask_cors import CORS

from pybiscus.flower.sessionlink import LINK_TRANSPORTS

LINK_TRANSPORT_ENV = "PYBISCUS_LINK_TRANSPORT"

from pybiscus.session.auth import SESSION_TOKEN_ENV, component_token, manager_token_names, print_access, require_tokens, tokens_required
from pybiscus.session.csrf import HEADER, require_pybiscus_header
from pybiscus.session import invitations, tls

# **************************

pybiscus_manager_app = Flask(__name__)
require_pybiscus_header(pybiscus_manager_app)
from pybiscus.session.limits import limit_request_size
limit_request_size(pybiscus_manager_app)
from pybiscus.session.framing import forbid_framing
forbid_framing(pybiscus_manager_app)
pybiscus.session.theme.install(pybiscus_manager_app)

admin_token = None     # the operator's: the manager's pages and actions
# the participants': registration, session parameters, webhooks. Created even when the manager
# requires none: an agent listening on the network requires it from the others
session_token = None
tokens_are_required = False

require_tokens(pybiscus_manager_app, "manager",
               enabled=lambda: tokens_are_required,
               cookie=lambda: f"pybiscus-manager-{manager_port}",
               access_token=lambda: admin_token,
               session_token=lambda: session_token,
               invitation=lambda token: invitations.invited_bouquet(manager_port, token),
               invitation_problem=lambda token: invitations.invitation_problem(manager_port, token),
               agent_invitation=lambda token: invitations.invited_agent(manager_port, token),
               agent_invitation_problem=lambda token: invitations.agent_invitation_problem(manager_port, token))

# the agents' pages call the manager from their own origin (registration, waiting for the session):
# the local ones are always allowed, those of other hosts through --allow-origin. The former "*"
# let any site open in the operator's browser read the manager and drive it
LOCAL_ORIGINS = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

# **************************

# global variable that contains the application context
registered_clients = {}
registered_servers = {}
registered_agents_meta = {}   # name -> {geo_location, bouquet, location, organisation, role, agent_url}
# name -> {url, role, bouquet, time}: the agents that reported their start (pybiscus_agent --config),
# shown until they register; not reset by a drop, they still run and register again
started_agents = {}
manager_port = None
# the bouquet this manager's session belongs to (--bouquet): the one its page shows, whatever the
# agents declare at their registration; None keeps showing theirs
bouquet = None
bouquet_color = None   # --color: a CSS colour; None derives one from the bouquet's name
# --bouquet-mismatch: an agent declaring another bouquet than --bouquet is refused, or only warned
# about: it has most likely registered with the wrong manager
bouquet_mismatch = "refuse"
link_transport = "directory"   # --link-transport
# lower-level bouquet -> the transport of its link, chosen in this manager's page (else link_transport)
link_transports = {}
manager_host = "127.0.0.1"   # --host: the address the manager listens on
machine_name = None   # --machine: the name of this manager's machine in the network view (default: its host name)
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
# --upper-token, or the invitation's: kept apart from upper_link, which the page shows
upper_token = None
# --invitation: the one this manager reports with (pybiscus.session.invitations.Invitation)
invitation = None
# --require-invitation: a lower level without an invitation is refused
require_invitation = False
# lower-level bouquet -> {"time", "reason"}: the reports refused, shown as unexpected sites
refused_lower_levels = {}
# --require-agent-invitation: an agent without an invitation is refused
require_agent_invitation = False
# agent name -> {"time", "reason", "role"}: the registrations refused, shown in the participants page
refused_agents = {}
# agent name -> the token it gave at its registration, which this manager presents when it calls it
agent_call_tokens = {}
serves_https = False
recording = None       # --record or the session form: pybiscus.session.manager.recording.Recording
browsed_url = None     # the manager's address from its own machine, where its recorder opens its page
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
    global agent_call_tokens
    agent_call_tokens = {}

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

def start_recording(directory, automatic=True):
    """--record (automatic), or the first session form asking for a recording; None if this machine cannot record"""
    from pathlib import Path
    from pybiscus.session.manager.recording import DEFAULT_DIRECTORY, Recording, missing_requirements
    global recording
    if missing_requirements():
        return None
    recording = Recording(Path(directory or DEFAULT_DIRECTORY), browsed_url, bouquet or f"manager-{manager_port}", admin_token,
                          no_agent=lambda: not registered_clients and not registered_servers, automatic=automatic)
    recording.start()
    atexit.register(recording.stop)
    return recording

def agent_headers(name: str) -> dict:
    """to call a registered agent: its call token. One registered without (by a script) gets the
    session token, which only an agent requiring no token lets through"""
    return {HEADER: "1", "Authorization": f"Bearer {agent_call_tokens.get(name) or session_token}"}

def flag_from_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")

def main():

    if sys.argv[1:2] and sys.argv[1] in invitations.COMMANDS:
        sys.exit(invitations.cli(sys.argv[1:]))

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
    parser.add_argument("--link-transport", choices=LINK_TRANSPORTS, default=os.environ.get(LINK_TRANSPORT_ENV, "directory"),
                        help="how the links to the lower levels are made, unless chosen per lower level in the page: a directory "
                             "their relay and server share on one machine, or this manager's mailbox, over HTTP, any machines "
                             f"(default: ${LINK_TRANSPORT_ENV}, else directory)")
    parser.add_argument("--color", default=None,
                        help="CSS colour of this manager's page (default: derived from --bouquet, the same for the same name)")
    parser.add_argument("--machine", default=None,
                        help="name of this manager's machine in the network view, and of its agents reached at the loopback "
                             "(default: the host name)")
    parser.add_argument("--location", default=None, help="where this manager is, e.g. palaiseau-dc (shown on the maps)")
    parser.add_argument("--geo", type=geo_coordinates, default=None,
                        help="this manager's coordinates, LAT,LON (default on the maps: next to its session's server)")
    parser.add_argument("--upper-url", default=None,
                        help="URL of the upper-level manager of a hierarchical session, e.g. http://localhost:5555: "
                             "this manager reports its bouquet's topology to it (requires --bouquet)")
    parser.add_argument("--upper-token", default=None,
                        help="session token of the upper-level manager (default: $PYBISCUS_UPPER_TOKEN, else its token file "
                             "when it runs on this machine, started from the same directory)")
    parser.add_argument("--record", nargs="?", const="experiments/recordings", default=None, metavar="DIR",
                        help="film each session from this manager's page (and the agents' run monitors) into DIR "
                             "(default experiments/recordings): rushes and video, by launch/doc/record_session.py; "
                             "needs uv, ffmpeg and the Chromium of Playwright")
    parser.add_argument("--require-token", action="store_true",
                        help="require the tokens on the loopback too (always required when listening beyond it)")
    parser.add_argument("--invitation", default=os.environ.get(invitations.INVITATION_ENV), metavar="FILE",
                        help="invitation of the upper-level manager (session_manager invite there): gives the upper level's "
                             "URL, this manager's bouquet and its token, instead of --upper-url, --bouquet and --upper-token "
                             f"(default: ${invitations.INVITATION_ENV})")
    parser.add_argument("--require-invitation", action="store_true", default=flag_from_env(invitations.REQUIRE_INVITATION_ENV),
                        help="refuse the lower-level managers without an invitation of this one (session_manager invite); "
                             f"requires the tokens (default: ${invitations.REQUIRE_INVITATION_ENV})")
    parser.add_argument("--require-agent-invitation", action="store_true",
                        default=flag_from_env(invitations.REQUIRE_AGENT_INVITATION_ENV),
                        help="refuse the agents without an invitation of this manager (session_manager invite --agent): "
                             f"the session token no longer registers one; requires the tokens "
                             f"(default: ${invitations.REQUIRE_AGENT_INVITATION_ENV})")
    tls.add_tls_arguments(parser)
    args = parser.parse_args()
    tls.check_tls_arguments(parser, args)
    # a default is not checked against the choices: the environment's is checked here
    if args.link_transport not in LINK_TRANSPORTS:
        parser.error(f"${LINK_TRANSPORT_ENV}={args.link_transport}: one of {', '.join(LINK_TRANSPORTS)} expected")
    invited = None
    if args.invitation:
        given = [option for option, value in (("--bouquet", args.bouquet), ("--upper-url", args.upper_url),
                                              ("--upper-token", args.upper_token)) if value]
        if given:
            parser.error(f"--invitation gives the bouquet, the upper level's URL and token: not with {', '.join(given)}")
        try:
            invited, warnings = invitations.read_invitation(args.invitation)
        except ValueError as e:
            parser.error(str(e))
        for warning in warnings:
            print(f"⚠️  {warning}", flush=True)
        args.bouquet, args.upper_url, args.upper_token = invited.bouquet, invited.upper_url, invited.token
    if args.upper_url and not args.bouquet:
        parser.error("--upper-url requires --bouquet: the upper-level manager tells its lower levels apart by their bouquet")

    CORS(pybiscus_manager_app, origins=[LOCAL_ORIGINS, *args.allow_origin], allow_headers=["Content-Type", "Authorization", HEADER])

    global browsed_url, manager_port, admin_token, session_token, tokens_are_required, bouquet, bouquet_color, bouquet_mismatch, link_transport, manager_host, machine_name, manager_url, manager_location, manager_geo
    global invitation, require_invitation, serves_https, require_agent_invitation
    invitation = invited
    require_invitation = args.require_invitation
    require_agent_invitation = args.require_agent_invitation
    manager_port=args.port
    manager_location, manager_geo = args.location, args.geo
    bouquet = args.bouquet
    bouquet_color = args.color
    bouquet_mismatch = args.bouquet_mismatch
    link_transport = args.link_transport
    manager_host = args.host
    machine_name = args.machine
    # without tokens, every request passes: the invitations would protect nothing
    tokens_are_required = tokens_required(args.host, args.require_token or args.require_invitation
                                          or args.require_agent_invitation)
    admin_name, session_name = manager_token_names(manager_port)
    admin_token = component_token(admin_name, args.admin_token) if tokens_are_required else None
    session_token = component_token(session_name, args.session_token)

    print(f"🚀 Manager starting on port {manager_port}" + (f", bouquet {bouquet}" if bouquet else ""))
    tls.trust_ca(*filter(None, (args.tls_ca, invitation_ca(invited))))
    warning = tls.plain_http_warning("manager", args.host, args)
    if warning:
        print(warning, flush=True)
    web_scheme = tls.scheme(args)
    browsed_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    browsed_url = f"{web_scheme}://{browsed_host}:{manager_port}"
    # listening on every interface, the other managers are elsewhere: they need the machine's name
    linked_host = socket.getfqdn() if args.host in ("0.0.0.0", "::") else browsed_host
    manager_url = f"{web_scheme}://{linked_host}:{manager_port}"
    serves_https = web_scheme == "https"
    invitations.record_manager(manager_port, manager_url, bouquet, serves_https, args.tls_ca)
    if require_invitation:
        print("📨 lower-level managers: an invitation of this one required (session_manager invite)", flush=True)
    if require_agent_invitation:
        print("🎫 agents: an invitation of this manager required (session_manager invite --agent)", flush=True)
    if invited:
        print(f"📨 invited by {invited.upper_bouquet} ({invited.upper_url}) as {invited.bouquet}, "
              f"until {invited.expires:%Y-%m-%d}", flush=True)
    print_access("manager", f"{browsed_url}/pybiscus-session/manage", admin_token)
    print(f"🔑 session token, for the agents (shown in the manager page too): {session_token}", flush=True)
    if args.record:
        from pybiscus.session.manager.recording import missing_requirements
        if missing_requirements():
            parser.error(f"--record needs {', '.join(missing_requirements())}")
        start_recording(args.record)
    if args.upper_url:
        from pybiscus.session.manager.upper_level import report_to_upper_level
        report_to_upper_level(args.upper_url, args.upper_token)
    pybiscus_manager_app.run(host=args.host, port=manager_port, ssl_context=tls.ssl_context(args))

def invitation_ca(invited):
    """the CA of the invitation, in a file requests can trust"""
    if invited is None:
        return None
    from pathlib import Path
    path = Path(".pybiscus-cache/tls") / f"invitation-ca-{manager_port}.pem"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(invited.ca_certificate, encoding="utf-8")
    return str(path)

# **************************

if __name__ == "__main__":
    main()
