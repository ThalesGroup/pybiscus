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

# **************************

@pybiscus_manager_app.route("/pybiscus-session/run", methods=["GET"])
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
     
    presets_raw = request.args.get("presets")
    
    if presets_raw:
        try:
            # decode and parse JSON param
            decoded = urllib.parse.unquote(presets_raw)

            # store them into context
            pybiscus.session.manager.session_manager.agent_gui_json_presets = json.loads(decoded)

            print("session back-end received session json presets: ", pybiscus.session.manager.session_manager.agent_gui_json_presets)

        except Exception as e:
            print( f"/pybiscus-session/run with bad param {str(e)}" )
            raise e

    else:
        print("/pybiscus-session/run with no param")

    # set the session running flag
    pybiscus.session.manager.session_manager.session_is_running = True

    return jsonify({ 
        "status": "success",
    }), 200

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

    custom_presets = pybiscus.session.manager.session_manager.agent_gui_json_presets.copy()

    custom_presets["values_set"]["client_run.cid"] = generate_new_cid();
    custom_presets["values_lock"] += [ "client_run.cid" ]    

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

    pybiscus.session.manager.session_manager.clear_session()

    # les buffers sont drainés par leurs GET respectifs, mais un drop pendant un run laisse
    # des messages non consommés : rechargée, la page les rejouerait et ressusciterait des
    # agents d'une session morte
    clear_message_buffers()

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agents", methods=["GET"])
def pybiscus_manager_list_clients():
    return jsonify({
        "clients": pybiscus.session.manager.session_manager.registered_clients,
        "servers": pybiscus.session.manager.session_manager.registered_servers,
        "meta":    pybiscus.session.manager.session_manager.registered_agents_meta,
    })

# **************************

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@pybiscus_manager_app.route("/pybiscus-session/manage")
def pybiscus_manager_manage():
    return render_template("pybiscus/manager.html", manager_port=pybiscus.session.manager.session_manager.manager_port)

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

    # état déclaré explicitement par l'agent (protocole AgentState) ; absent des logs
    # purement informatifs, auquel cas le front retombe sur l'analyse du texte
    state = data.get('state')

    # private section
    with agent_lock:
        agent_messages.append({'source': source, 'message': message, 'state': state})

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

# *************************************
# *** Pybiscus vignettes management ***
# *************************************

new_vignettes = []
vignettes_lock = Lock()  # lock used to prevent logs concurrent access

# cache d'affichage du manager ; les vignettes de référence sont dans experiments/<session>
VIGNETTES_DIR = "pybiscus/session/manager/static/pybiscus/vignettes"

@pybiscus_manager_app.route('/webhook/vignettes', methods=['POST'])
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
    save_path = os.path.join(VIGNETTES_DIR, f"grid_{col_row}.png")
    os.makedirs(VIGNETTES_DIR, exist_ok=True)
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
        for vignette in glob.glob(os.path.join(VIGNETTES_DIR, "grid_*.png")):
            try:
                os.remove(vignette)
            except OSError as e:
                logm.console.log(f"vignette removal failed: {vignette} ({e})")
