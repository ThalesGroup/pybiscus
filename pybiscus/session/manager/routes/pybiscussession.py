import copy
import os
import glob
import json
from flask import render_template, request, jsonify
import requests
from threading import Lock

import urllib
import pybiscus.session.manager.session_manager
from pybiscus.session.manager.session_manager import generate_new_cid, pybiscus_manager_app
import pybiscus.core.pybiscus_logger as logm
from pybiscus.session.auth import session_access
from pybiscus.session.csrf import HEADER
from pybiscus.session.manager import cycles

# **************************

@pybiscus_manager_app.route("/pybiscus-session/run", methods=["POST"])
def pybiscus_manager_run_session():
    """    an optional "presets" of type json customizes the html :
    - options values to be set
    - options to be locked to the active value (change not permitted)

    Format to know which actions to perform : 

    {
        "options_set": {
            "model" : "Cifar 10",
            "data" : "Cifar 10"
            "ssl" : "None",
        },

        "options_lock": [ "model", "data", "ssl" ]
    }
    """
     
    from pybiscus.session.manager.upper_level import (apply_upper_constraints, links_for_lower_levels, missing_relays,
                                                      record_session_constraints, upper_constraints, upper_level_session_link)

    # a lower level of a hierarchical session follows its upper level's session
    if pybiscus.session.manager.session_manager.upper_link is not None and upper_constraints() is None:
        return jsonify({"status": "error",
                        "message": "the upper-level session is not configured yet: its model, data and number of rounds come first"}), 409
    if pybiscus.session.manager.session_manager.upper_link is not None and upper_level_session_link() is None:
        return jsonify({"status": "error",
                        "message": "the upper-level session has no link for this level: is it relayed?"}), 409
    # an upper level: every lower level reaches it through one of its clients
    missing = missing_relays()
    if missing:
        return jsonify({"status": "error",
                        "message": "designate a relay client for every lower level (Topology): " + ", ".join(missing)}), 409

    presets_raw = request.args.get("presets")
    
    if presets_raw:
        try:
            # decode and parse JSON param
            decoded = urllib.parse.unquote(presets_raw)

            presets = json.loads(decoded)
            if pybiscus.session.manager.session_manager.upper_link is not None:
                apply_upper_constraints(presets)
            # the lower levels' servers stop after as many rounds: none may wait for a round that never comes
            if pybiscus.session.manager.session_manager.lower_levels and not presets.get("num_rounds"):
                return jsonify({"status": "error",
                                "message": "a session with lower levels sets num_rounds in its session form: they follow it round for round"}), 409
            record_session_constraints(presets)

            # store them into context
            pybiscus.session.manager.session_manager.agent_gui_json_presets = presets

            print("session back-end received session json presets: ", pybiscus.session.manager.session_manager.agent_gui_json_presets)

        except Exception as e:
            print( f"/pybiscus-session/run with bad param {str(e)}" )
            raise e

    else:
        print("/pybiscus-session/run with no param")

    # the clients taking part: their order gives their cid and their share of the data; the relays
    # take part without data, their cids after the others'
    session = pybiscus.session.manager.session_manager
    session.session_relays = [client for client in session.registered_clients if client in session.relays.values()]
    session.session_clients = [client for client in session.registered_clients if client not in session.session_relays]
    session.session_links = links_for_lower_levels()
    session.upper_session_link = upper_level_session_link()
    cycles.reset()
    if session.upper_link is not None:
        session.upper_link["dropped"] = None

    # set the session running flag
    pybiscus.session.manager.session_manager.session_is_running = True

    return jsonify({ 
        "status": "success",
    }), 200

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agent", methods=["POST"])
@session_access
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

    # métadonnées transmises par le formulaire de registration (déjà envoyées, jusqu'ici ignorées)
    pybiscus.session.manager.session_manager.registered_agents_meta[name] = {
        "role": role,
        "agent_url": agent_url,
        "geo_location": data.get("geo_location"),
        "bouquet": data.get("bouquet"),
        "location": data.get("location"),
        "organisation": data.get("organisation"),
    }

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

        pybiscus.session.manager.session_manager.registered_clients_cpu[name] = {
            "machine": data.get("machine"), "cpu_cores": data.get("cpu_cores"),
        }
        pybiscus.session.manager.session_manager.registered_clients[name] = agent_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
        })

    else:
        return jsonify({"status": "error", "message": f"Bad role={role}, it should be server or client"}), 400

# **************************

@pybiscus_manager_app.route("/pybiscus-session/params", methods=["GET"])
@session_access
def pybiscus_manager_get_session_params():

    from pybiscus.session.manager.upper_level import RELAY_LINK, RELAY_OPTION, SERVER_LINK, link_presets

    if not pybiscus.session.manager.session_manager.session_is_running:
        return jsonify({"status": "error", "message": "session is not running yet"})

    session = pybiscus.session.manager.session_manager
    # a deep copy: the shallow one let "values_lock +=" extend the shared presets at every call
    custom_presets = copy.deepcopy(session.agent_gui_json_presets) or {}
    for key, empty in (("options_set", {}), ("options_lock", []), ("values_set", {}), ("values_lock", [])):
        custom_presets.setdefault(key, empty)
    data_partition = custom_presets.pop("data_partition", None)
    data_holdout = custom_presets.pop("data_holdout", None)
    share_cpu_threads = custom_presets.pop("share_cpu_threads", False)
    # the relays are Flower clients too: every round waits for them
    min_clients = custom_presets.pop("min_clients", None) or len(session.session_clients) + len(session.session_relays)
    robustness = custom_presets.pop("robustness", None)
    num_rounds = custom_presets.pop("num_rounds", None)

    # each call used to take a new cid: the server's page and every reload consumed one, and the
    # cids of the clients were neither consecutive nor stable. Pages name their agent now.
    agent = request.args.get("agent")
    index = None
    if agent is None:
        cid = generate_new_cid()
    elif agent in session.registered_servers:
        cid = None
    elif agent in session.session_clients:
        index = session.session_clients.index(agent)
        cid = str(index)
    elif agent in session.session_relays:
        # no share of the data, no holdout, no CPU threads (index stays None): it computes nothing
        cid = str(len(session.session_clients) + session.session_relays.index(agent))
        relayed = next(bouquet for bouquet, relay in session.relays.items() if relay == agent)
        # named, not only Some: another client plugin loaded (byzantine...) could be the first tab
        custom_presets["options_set"]["flower_client.alternate_client_class"] = RELAY_OPTION
        custom_presets["options_lock"].append("flower_client.alternate_client_class")
        link_presets(custom_presets, RELAY_LINK, session.session_links[relayed])
        logm.console.log(f"🔁 {agent} relays the lower level {relayed}")
    else:
        cid = session.late_client_cids.setdefault(agent, str(len(session.session_clients) + len(session.late_client_cids)))
        if data_partition:
            logm.console.log(f"⚠️ {agent} registered after the session launch: it gets no share of the data partition")

    # Flower's default of 2 let a session of 7 clients run its first rounds with the first 2 to
    # connect, and robust aggregations count on n
    if agent in session.registered_servers and min_clients:
        for name in ("min_fit_clients", "min_evaluate_clients", "min_available_clients"):
            custom_presets["values_set"][f"server_strategy.strategy.config.{name}"] = min_clients
            custom_presets["values_lock"].append(f"server_strategy.strategy.config.{name}")
    if agent in session.registered_servers and num_rounds:
        custom_presets["values_set"]["server_run.num_rounds"] = num_rounds
        custom_presets["values_lock"].append("server_run.num_rounds")
    if agent in session.registered_servers and session.upper_session_link:
        # " " selects Some for an Optional[T] (see set_option)
        custom_presets["options_set"][SERVER_LINK] = " "
        custom_presets["options_lock"].append(SERVER_LINK)
        link_presets(custom_presets, SERVER_LINK, session.upper_session_link)
    if agent in session.registered_servers and robustness:
        custom_presets["values_set"]["server_strategy.robustness"] = robustness
        custom_presets["values_lock"].append("server_strategy.robustness")

    # the webhooks of the agents' runs reach this manager, at the address the agent reached it by
    custom_presets["values_set"]["manager_url"] = request.host_url.rstrip("/")
    custom_presets["values_lock"].append("manager_url")

    # proposed, not locked: a session's reports in a directory of its bouquet, so that two
    # sessions on one machine do not share experiments/current
    if agent in session.registered_servers and session.bouquet:
        custom_presets["values_set"]["server_run.reporting.basedir"] = "${root_dir}/experiments/" + session.bouquet

    if cid is not None:
        custom_presets["values_set"]["client_run.cid"] = cid
        custom_presets["values_lock"].append("client_run.cid")

    # not locked: the operator may still adjust a client's threads
    threads = session.client_threads(agent) if share_cpu_threads and index is not None else None
    if threads is not None:
        # " " selects Some for an Optional[T] (see set_option)
        custom_presets["options_set"]["client_compute_context.num_threads"] = " "
        custom_presets["values_set"]["client_compute_context.num_threads"] = threads

    if data_partition and index is not None:
        prefix = "data.config.train.partition"
        # " " selects Some for an Optional[T] (see set_option)
        custom_presets["options_set"][prefix] = " "
        custom_presets["options_lock"].append(prefix)
        values = {**data_partition, "num_partitions": len(session.session_clients), "partition_id": index}
        for name, value in values.items():
            custom_presets["values_set"][f"{prefix}.{name}"] = value
            custom_presets["values_lock"].append(f"{prefix}.{name}")

    # every client, late ones included: the holdout draws from the client's own share, whatever it is
    if data_holdout and cid is not None and agent not in session.session_relays:
        prefix = "data.config.val"
        values = {"source": "holdout", **data_holdout}
        for name, value in values.items():
            custom_presets["values_set"][f"{prefix}.{name}"] = value
            custom_presets["values_lock"].append(f"{prefix}.{name}")

    first_server_item = next(iter(pybiscus.session.manager.session_manager.registered_servers.items()))
    _, server_url = first_server_item

    return jsonify({
        "status"     : "success",
        "message"    : "session is running",
        "server_url" : server_url,
        "presets"    : custom_presets,
    })

# **************************

@pybiscus_manager_app.route("/pybiscus-session/params", methods=["DELETE"])
def pybiscus_manager_delete_session():

    drop_session()
    return jsonify({"status": "success"}), 200


def stop_agent_runs():
    """a dropped session's runs stop with it: they went on without a manager, and a lower level's
    server waited for a model that no longer comes"""
    session = pybiscus.session.manager.session_manager
    headers = {HEADER: "1", "Authorization": f"Bearer {session.session_token}"}
    for name, url in {**session.registered_servers, **session.registered_clients}.items():
        try:
            response = requests.post(f"{url.rstrip('/')}/run/stop", headers=headers, timeout=5)
        except requests.RequestException as error:
            logm.console.log(f"⚠️ {name}: its run could not be stopped ({type(error).__name__})")
            continue
        if response.status_code == 202:
            logm.console.log(f"🛑 {name}: run stopped with the session")
        elif response.status_code != 409:
            logm.console.log(f"⚠️ {name}: its run could not be stopped (HTTP {response.status_code})")


def drop_session():
    stop_agent_runs()
    cycles.reset()
    pybiscus.session.manager.session_manager.clear_session()

    # les buffers sont drainés par leurs GET respectifs, mais un drop pendant un run laisse
    # des messages non consommés : rechargée, la page les rejouerait et ressusciterait des
    # agents d'une session morte
    clear_message_buffers()

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agents", methods=["GET"])
def pybiscus_manager_list_clients():
    from pybiscus.session.manager.upper_level import lower_levels, manager_place, upper_level
    return jsonify({
        "clients": pybiscus.session.manager.session_manager.registered_clients,
        "servers": pybiscus.session.manager.session_manager.registered_servers,
        "meta":    pybiscus.session.manager.session_manager.registered_agents_meta,
        "lower_levels": lower_levels(),
        "upper_level": upper_level(),
        "manager": manager_place(),
        "relays": pybiscus.session.manager.session_manager.relays,
        "session_running": pybiscus.session.manager.session_manager.session_is_running,
        "cycles": cycles.session_cycles(),
    })

# **************************

# the operator designates, for a lower level, the client of this session that relays it
@pybiscus_manager_app.route("/pybiscus-session/relays", methods=["POST"])
def pybiscus_manager_designate_relay():
    from pybiscus.session.manager.upper_level import designate_relay
    session = pybiscus.session.manager.session_manager
    data = request.get_json(silent=True) or {}
    bouquet, client = data.get("bouquet"), data.get("client") or None
    if session.session_is_running:
        return jsonify({"status": "error", "message": "the session is running: drop it to change its relays"}), 409
    with session.lower_levels_lock:
        known = bouquet in session.lower_levels
    if not known:
        return jsonify({"status": "error", "message": f"no lower level named {bouquet!r}"}), 400
    if client is not None and client not in session.registered_clients:
        return jsonify({"status": "error", "message": f"no client named {client!r} in this session"}), 400
    designate_relay(bouquet, client)
    return jsonify({"status": "ok", "relays": session.relays})

# **************************

# a lower-level manager (started with --upper-url) reports its bouquet's topology here
@pybiscus_manager_app.route("/pybiscus-session/lower-level", methods=["POST"])
@session_access
def pybiscus_manager_receive_lower_level():
    from pybiscus.session.manager.upper_level import record_lower_level
    topology = request.get_json(silent=True)
    if not isinstance(topology, dict) or not isinstance(topology.get("bouquet"), str) or not topology["bouquet"] \
            or not isinstance(topology.get("agents"), list):
        return jsonify({"status": "error", "message": "expected a bouquet name and a list of agents"}), 400
    record_lower_level(topology)
    # the lower level shows which upper level it reports to, in its colour
    from pybiscus.session.manager.upper_level import session_for_lower_levels
    return jsonify({"status": "ok", "bouquet": pybiscus.session.manager.session_manager.bouquet,
                    "color": pybiscus.session.manager.session_manager.bouquet_color, "session": session_for_lower_levels(topology["bouquet"])})

# between two changes of its topology, a lower-level manager only says it is alive
@pybiscus_manager_app.route("/pybiscus-session/lower-level/heartbeat", methods=["POST"])
@session_access
def pybiscus_manager_lower_level_heartbeat():
    from pybiscus.session.manager.upper_level import lower_level_alive
    bouquet = (request.get_json(silent=True) or {}).get("bouquet")
    if not isinstance(bouquet, str) or not bouquet:
        return jsonify({"status": "error", "message": "expected a bouquet name"}), 400
    from pybiscus.session.manager.upper_level import session_for_lower_levels
    return jsonify({"status": "ok", "known": lower_level_alive(bouquet),
                    "bouquet": pybiscus.session.manager.session_manager.bouquet,
                    "color": pybiscus.session.manager.session_manager.bouquet_color, "session": session_for_lower_levels(bouquet)})

# **************************

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@pybiscus_manager_app.route("/pybiscus-session/manage")
def pybiscus_manager_manage():
    from pybiscus.core.gui_events import gui_log_patterns
    from pybiscus.session.agent.agent_weblog import agent_state_protocol
    return render_template("pybiscus/manager.html", manager_port=pybiscus.session.manager.session_manager.manager_port,
                           session_token=pybiscus.session.manager.session_manager.session_token,
                           bouquet=pybiscus.session.manager.session_manager.bouquet,
                           bouquet_color=pybiscus.session.manager.session_manager.bouquet_color,
                           flower_port=pybiscus.session.manager.session_manager.proposed_flower_port(),
                           gui_log_patterns=gui_log_patterns(), agent_state_protocol=agent_state_protocol())

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
@session_access
def pybiscus_manager_receive_agents():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # état déclaré explicitement par l'agent (protocole AgentState) ; absent des logs
    # purement informatifs, auquel cas le front retombe sur l'analyse du texte
    state = data.get('state')

    # private section
    with agent_lock:
        agent_messages.append({'source': source, 'message': message, 'state': state})

    # the source is "<bouquet>:<agent name>", as the page reads it (checkAgentLogs)
    if state and ":" in source:
        pybiscus.session.manager.session_manager.agent_states[source.split(":", 1)[1]] = state

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
@session_access
def pybiscus_manager_receive_log():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # private section
    with log_lock:
        log_messages.append({'source': source, 'message': message})
    cycles.note_server_line(message)

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
@session_access
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

# *************************************
# *** Pybiscus vignettes management ***
# *************************************

new_vignettes = []
vignettes_lock = Lock()  # lock used to prevent logs concurrent access

# cache d'affichage du manager ; les vignettes de référence sont dans experiments/<session>.
# Un dossier par port, sous le dossier static du paquet (et non relatif au répertoire courant) :
# deux managers lancés depuis le même dépôt (niveaux supérieur et inférieur d'une session
# hiérarchique) écrasaient les vignettes l'un de l'autre, et le ménage de l'un vidait l'autre.
def vignettes_dir():
    return os.path.join(pybiscus_manager_app.static_folder, "pybiscus", "vignettes",
                        str(pybiscus.session.manager.session_manager.manager_port))

@pybiscus_manager_app.route('/webhook/vignettes', methods=['POST'])
@session_access
def pybiscus_manager_post_vignette():
    
    # check file presence
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # get metadata
    if "metadata" in request.form:
        metadata = json.loads(request.form["metadata"])
        col = metadata["col"]
        row = metadata["row"]
        col_row = f"{col}_{row}"
    else:
        metadata = None

    # save file
    save_path = os.path.join(vignettes_dir(), f"grid_{col_row}.png")
    os.makedirs(vignettes_dir(), exist_ok=True)
    file.save(save_path)

    # memo file
    with vignettes_lock:
        new_vignettes.append( col_row )

    return jsonify({
        "status": "ok",
        "filename": file.filename,
        "metadata": metadata
    })

# **************************

@pybiscus_manager_app.route('/pybiscus-session/vignettes', methods=['GET'])
def pybiscus_manager_get_new_vignettes():

    with vignettes_lock:
        global new_vignettes
        _new_vignettes = new_vignettes
        new_vignettes = []

    # return json encoded vignettes
    return jsonify(_new_vignettes)

# *****************************
# *** Session reset support ***
# *****************************

def clear_message_buffers():
    """Vide tout ce qu'un agent ou un run a pu déposer, pour repartir d'une page vierge."""

    global agent_messages, log_messages, metrics_messages, new_vignettes

    with agent_lock:
        agent_messages = []

    with log_lock:
        log_messages = []

    with metrics_lock:
        metrics_messages = []

    with vignettes_lock:
        new_vignettes = []

        # les png du run précédent sont un cache d'affichage : l'original est archivé
        # dans experiments/<session>. Sans ce ménage ils survivent jusqu'à être écrasés,
        # et une session plus courte laisserait voir les vignettes de la précédente.
        for vignette in glob.glob(os.path.join(vignettes_dir(), "grid_*.png")):
            try:
                os.remove(vignette)
            except OSError as e:
                logm.console.log(f"vignette removal failed: {vignette} ({e})")
