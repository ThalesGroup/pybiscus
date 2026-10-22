import copy
import re
import time
import os
import glob
import json
import threading
from typing import Optional
from flask import render_template, request, jsonify
import requests

import urllib
import pybiscus.session.manager.session_manager
from pybiscus.session.manager.session_manager import generate_new_cid, pybiscus_manager_app
import pybiscus.core.pybiscus_logger as logm
from pybiscus.session.auth import headers_for, session_access
from pybiscus.session.csrf import HEADER
from pybiscus.session.manager import cycles, repetition
from pybiscus.core.gui_events import gui_log_patterns
from pybiscus.session.manager.feeds import Feed

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
            # the agents would ignore them: said here, under the field of the session form
            from pybiscus.session.interpolation import resolver_paths
            calling = resolver_paths(presets)
            if calling:
                return refused([{"loc": path.split(".", 1)[1].split(".") if path.startswith(("values_set.", "options_set.")) else path.split("."),
                                 "msg": "an interpolation calling a resolver (${oc.env:…}) would read the agents' machines: "
                                        "the agents ignore it"} for path in calling]), 409
            repeat = presets.get("repeat")
            if repeat is not None:
                problems = repetition_refused(repeat)
                if problems:
                    return refused(problems), 409
            if presets.get("record"):
                problems = recording_refused()
                if problems:
                    return refused(problems), 409
            if pybiscus.session.manager.session_manager.upper_link is not None:
                apply_upper_constraints(presets)
            # the lower levels' servers stop after as many rounds: none may wait for a round that never comes
            if pybiscus.session.manager.session_manager.lower_levels and not presets.get("num_rounds"):
                return refused([{"loc": ["num_rounds"],
                                 "msg": "a session with lower levels sets num_rounds in its session form: they follow it round for round"}]), 409
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
    # --record films every session; the form's record, the sessions asking for it
    if session.recording is not None and session.recording.automatic:
        session.recording.session_launched()
    elif (session.agent_gui_json_presets or {}).get("record"):
        (session.recording or session.start_recording(None, automatic=False)).session_launched()

    repeat = (session.agent_gui_json_presets or {}).get("repeat")
    if repeat is not None:
        from pybiscus.core.schedule import ConfigSchedule
        repetition.start(ConfigSchedule.model_validate(repeat))
    else:
        repetition.cancel()

    return jsonify({ 
        "status": "success",
    }), 200

def refused(problems: list):
    """a refused session form: each problem as the check's errors ({loc, msg}), which the form shows
    under its field, and as one message for a caller without the form"""
    message = "; ".join(f"{'.'.join(map(str, p['loc']))}: {p['msg']}" if p["loc"] else p["msg"] for p in problems)
    return jsonify({"status": "error", "message": message, "fields": problems})


def recording_refused() -> list:
    """why the manager cannot record the session, as the check's errors; empty if it can"""
    from pybiscus.session.manager.recording import missing_requirements
    missing = missing_requirements()
    if missing:
        return [{"loc": ["record"], "msg": f"the manager's machine cannot record: it needs {', '.join(missing)}"}]
    return []


def repetition_refused(repeat) -> list:
    """why a session cannot be launched again at deadlines, as the check's errors; empty if it can"""
    from pydantic import ValidationError
    from pybiscus.core.schedule import ConfigSchedule
    session = pybiscus.session.manager.session_manager
    # each level of a tree is launched by its own operator, its rounds following its upper level's
    if session.upper_link is not None or session.lower_levels:
        return [{"loc": ["repeat"],
                 "msg": "a hierarchical session cannot be launched again at deadlines yet: repeat a session without lower or upper level"}]
    try:
        ConfigSchedule.model_validate(repeat)
    except ValidationError as error:
        return [{"loc": ["repeat", *e["loc"]], "msg": e["msg"]}
                for e in error.errors(include_url=False, include_context=False, include_input=False)]
    return []

# **************************

def is_web_url(url) -> bool:
    """an agent's URL ends in the manager's page, as a link and as the session form's frame: a
    javascript: one would run in that page"""
    if not isinstance(url, str):
        return False
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


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
    if not is_web_url(agent_url):
        return jsonify({"status": "error", "message": f"agent_url {agent_url!r}: an http:// or https:// URL is expected"}), 400

    role = data.get("role")

    if role is None:
        return jsonify({"status": "error", "message": "Missing 'role'"}), 400

    sm = pybiscus.session.manager.session_manager
    declared = data.get("bouquet") or sm.bouquet
    warning = None
    if sm.bouquet and declared != sm.bouquet:
        problem = (f"this session is the bouquet '{sm.bouquet}', the agent '{name}' declares '{declared}': "
                   f"is it registering with the right manager?")
        if sm.bouquet_mismatch == "refuse":
            logm.console.log(f"⛔ registration of {name} refused: {problem}")
            return jsonify({"status": "error", "message": problem, "expected_bouquet": sm.bouquet}), 409
        warning = problem
        logm.console.log(f"⚠️ {problem}")
    from pybiscus.session.tls import plain_agent_warning
    plain = plain_agent_warning(sm.manager_url, agent_url, name)
    if plain:
        warning = f"{warning}; {plain}" if warning else plain
        logm.console.log(f"⚠️ {plain}")

    # métadonnées transmises par le formulaire de registration (déjà envoyées, jusqu'ici ignorées)
    pybiscus.session.manager.session_manager.registered_agents_meta[name] = {
        "role": role,
        "agent_url": agent_url,
        "geo_location": data.get("geo_location"),
        "bouquet": declared,
        "location": data.get("location"),
        "organisation": data.get("organisation"),
        # the machine it runs on, as it names itself: the addresses say localhost on one machine
        "machine": data.get("machine"),
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
            **({"warning": warning} if warning else {}),
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
            **({"warning": warning} if warning else {}),
        })

    else:
        return jsonify({"status": "error", "message": f"Bad role={role}, it should be server or client"}), 400

# **************************

# called by an agent's registration form: the bouquet of the session it is about to join, which the
# form then sets and locks (the registration of another one is refused or warned about)
@pybiscus_manager_app.route("/pybiscus-session/identity", methods=["GET"])
@session_access
def pybiscus_manager_identity():
    sm = pybiscus.session.manager.session_manager
    return jsonify({"bouquet": sm.bouquet, "color": sm.bouquet_color, "location": sm.manager_location,
                    "bouquet_mismatch": sm.bouquet_mismatch})

# **************************

def session_cid(agent: str) -> Optional[str]:
    """the cid the session gives an agent, None for a server or a client yet unknown; a late
    client's is taken when its page reads the session's params"""
    session = pybiscus.session.manager.session_manager
    if agent in session.session_clients:
        return str(session.session_clients.index(agent))
    if agent in session.session_relays:
        return str(len(session.session_clients) + session.session_relays.index(agent))
    return session.late_client_cids.get(agent)


def session_cids() -> dict[str, str]:
    session = pybiscus.session.manager.session_manager
    agents = list(session.session_clients) + list(session.session_relays) + list(session.late_client_cids)
    return {agent: session_cid(agent) for agent in agents}

# **************************

@pybiscus_manager_app.route("/pybiscus-session/params", methods=["GET"])
@session_access
def pybiscus_manager_get_session_params():

    from pybiscus.session.manager.upper_level import RELAY_LINK, RELAY_OPTION, SERVER_LINK, link_for_own_server, link_presets

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
    repeat = custom_presets.pop("repeat", None)
    custom_presets.pop("record", None)

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
        cid = session_cid(agent)
    elif agent in session.session_relays:
        # no share of the data, no holdout, no CPU threads (index stays None): it computes nothing
        cid = session_cid(agent)
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
        link_presets(custom_presets, SERVER_LINK, link_for_own_server(session.upper_session_link))
    # each session of the repetition goes on from the previous one's weights, and ends at once when
    # no client has new data
    if agent in session.registered_servers and repeat is not None:
        # " " selects Some for an Optional[T] (see set_option)
        for prefix in ("server_run.reporting.save_on_train_end", "server_run.weights_path"):
            custom_presets["options_set"][prefix] = " "
            custom_presets["options_lock"].append(prefix)
        for name, value in (("server_run.weights_path", "latest"), ("server_run.stop_without_new_data", True)):
            custom_presets["values_set"][name] = value
            custom_presets["values_lock"].append(name)
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


@pybiscus_manager_app.route("/pybiscus-session/stop-after-round", methods=["POST"])
def pybiscus_manager_stop_after_round():
    session = pybiscus.session.manager.session_manager
    if not session.session_is_running:
        return jsonify({"status": "error", "message": "no session is running"}), 409
    # its lower levels follow the end of its rounds through their links; a lower level ending first
    # would leave its upper level waiting for its aggregate
    if session.upper_link is not None:
        return jsonify({"status": "error", "message":
                        "a lower level runs the rounds of its upper level: stop the session from the upper level's manager"}), 409

    headers = {HEADER: "1", "Authorization": f"Bearer {session.session_token}"}
    stopping = []
    for name, url in session.registered_servers.items():
        try:
            response = requests.post(f"{url.rstrip('/')}/run/stop-after-round", headers=headers, timeout=5)
        except requests.RequestException as error:
            logm.console.log(f"⚠️ {name}: its run could not be stopped after its round ({type(error).__name__})")
            continue
        if response.status_code == 202:
            logm.console.log(f"🛑 {name}: its run stops after the current round")
            stopping.append(name)
        else:
            logm.console.log(f"⚠️ {name}: its run could not be stopped after its round (HTTP {response.status_code})")

    if not stopping:
        return jsonify({"status": "error", "message": "no server run could be stopped after its round"}), 409
    return jsonify({"status": "success", "servers": stopping}), 202


# the current session goes on to its end; no other one is launched
@pybiscus_manager_app.route("/pybiscus-session/stop-repeating", methods=["POST"])
def pybiscus_manager_stop_repeating():
    if repetition.repetition is None or repetition.repetition.status in (repetition.ENDED, repetition.FAILED):
        return jsonify({"status": "error", "message": "the session is not launched again at deadlines"}), 409
    repetition.repetition.request_stop()
    return jsonify({"status": "success", "repetition": repetition.state()}), 202


# the page's record button: a recording now, whatever the session's state; stop ends the one going
@pybiscus_manager_app.route("/pybiscus-session/recording/start", methods=["POST"])
def pybiscus_manager_start_recording():
    session = pybiscus.session.manager.session_manager
    problems = recording_refused()
    if problems:
        return jsonify({"status": "error", "message": problems[0]["msg"]}), 409
    recording = session.recording or session.start_recording(None, automatic=False)
    if not recording.start_now():
        return jsonify({"status": "error", "message": "a recording is already going"}), 409
    return jsonify({"status": "success", "recording": recording.state()}), 202


@pybiscus_manager_app.route("/pybiscus-session/recording/stop", methods=["POST"])
def pybiscus_manager_stop_recording():
    recording = pybiscus.session.manager.session_manager.recording
    if recording is None or not recording.stop_current():
        return jsonify({"status": "error", "message": "no recording is going"}), 409
    return jsonify({"status": "success", "recording": recording.state()}), 202


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
    repetition.cancel()
    stop_agent_runs()
    cycles.reset()
    pybiscus.session.manager.session_manager.clear_session()

    # les pages relisent les flux depuis le début à leur chargement : sans ce ménage, la page
    # rechargée après le drop rejouerait la session morte et en ressusciterait les agents
    clear_message_buffers()

# **************************

@pybiscus_manager_app.route("/pybiscus-session/agents", methods=["GET"])
def pybiscus_manager_list_clients():
    from pybiscus.flower.sessionlink import LINK_TRANSPORTS
    from pybiscus.session.manager.upper_level import lower_levels, manager_place, session_state, transport_of, upper_level
    return jsonify({
        "clients": pybiscus.session.manager.session_manager.registered_clients,
        "servers": pybiscus.session.manager.session_manager.registered_servers,
        "meta":    pybiscus.session.manager.session_manager.registered_agents_meta,
        "started": unregistered_started_agents(),
        "states":  pybiscus.session.manager.session_manager.agent_states,
        "lower_levels": lower_levels(),
        "upper_level": upper_level(),
        "manager": manager_place(),
        "relays": pybiscus.session.manager.session_manager.relays,
        "link_transports": {lower: transport_of(lower) for lower in pybiscus.session.manager.session_manager.lower_levels},
        "link_transport_choices": list(LINK_TRANSPORTS),
        "session_running": pybiscus.session.manager.session_manager.session_is_running,
        "cycles": cycles.session_cycles(),
        "repetition": repetition.state(),
        "recording": session_recording_state(),
        "session": session_state(),
        # the metrics feed names the clients by cid
        "cids": session_cids(),
    })

def session_recording_state():
    """None: nothing recorded yet; "unavailable": why this machine cannot record"""
    recording = pybiscus.session.manager.session_manager.recording
    if recording is not None:
        return recording.state()
    problems = recording_refused()
    return {"state": "idle", "unavailable": problems[0]["msg"]} if problems else None

def unregistered_started_agents() -> dict:
    session = pybiscus.session.manager.session_manager
    unregistered = {name: agent for name, agent in session.started_agents.items()
                    if name not in session.registered_servers and name not in session.registered_clients}
    for agent in unregistered.values():
        check_reachable(agent)
    return {name: {key: value for key, value in agent.items() if key != "checking"}
            for name, agent in unregistered.items()}


STARTED_CHECK_EVERY = 15   # seconds

def check_reachable(agent: dict) -> None:
    """an agent stopped before registering said nothing: the manager asks it, in the background so
    that the page's poll does not wait for a timeout"""
    if agent.get("checking") or not agent.get("url") or time.time() - agent.get("checked", 0) < STARTED_CHECK_EVERY:
        return
    agent["checking"] = True

    def ask():
        try:
            # any answer, a refusal or a login page included, says the agent runs
            requests.get(f"{agent['url'].rstrip('/')}/run/status", headers=headers_for(agent["url"]),
                         timeout=3, allow_redirects=False)
            agent["reachable"] = True
        except requests.RequestException:
            # marked, not removed: a firewall can stop the manager's requests and let the agent's
            # webhooks through, and such an agent can still be registered
            agent["reachable"] = False
        agent["checked"] = time.time()
        agent["checking"] = False

    threading.Thread(target=ask, daemon=True).start()

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

# the page of the network view
@pybiscus_manager_app.route("/pybiscus-session/network", methods=["GET"])
def pybiscus_manager_network_page():
    return render_template("pybiscus/network.html", bouquet=pybiscus.session.manager.session_manager.bouquet)


# the network view of the session: machines, listening processes, flows (the whole session at the head manager)
@pybiscus_manager_app.route("/pybiscus-session/network.json", methods=["GET"])
def pybiscus_manager_network():
    from pybiscus.session.manager.network import network_view
    return jsonify(network_view())


# the flows between two machines, as a firewall request needs them
@pybiscus_manager_app.route("/pybiscus-session/network.csv", methods=["GET"])
def pybiscus_manager_network_csv():
    import csv
    import io
    from pybiscus.session.manager.network import network_view
    view = network_view()
    machine = {p["id"]: p["machine"] for p in view["processes"]}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["from machine", "to machine", "port", "protocol", "purpose"])
    rows = sorted({(machine.get(f["from"], "?"), machine.get(f["to"], "?"), f["port"] or "", f["protocol"], f["purpose"])
                   for f in view["flows"] if f["port"] and machine.get(f["from"]) != machine.get(f["to"])},
                  key=lambda r: tuple(str(x) for x in r))
    writer.writerows(rows)
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8",
                                 "Content-Disposition": "attachment; filename=pybiscus-flows.csv"}

# **************************

# the transport of a lower level's link, chosen in this manager's page before the launch
@pybiscus_manager_app.route("/pybiscus-session/link-transports", methods=["POST"])
def pybiscus_manager_choose_link_transport():
    from pybiscus.flower.sessionlink import LINK_TRANSPORTS
    session = pybiscus.session.manager.session_manager
    data = request.get_json(silent=True) or {}
    bouquet, transport = data.get("bouquet"), data.get("transport") or None
    if session.session_is_running:
        return jsonify({"status": "error", "message": "the session is running: drop it to change its links"}), 409
    with session.lower_levels_lock:
        known = bouquet in session.lower_levels
    if not known:
        return jsonify({"status": "error", "message": f"no lower level named {bouquet!r}"}), 400
    if transport is not None and transport not in LINK_TRANSPORTS:
        return jsonify({"status": "error", "message": f"transport {transport!r}: one of {', '.join(LINK_TRANSPORTS)} expected"}), 400
    if transport is None:
        session.link_transports.pop(bouquet, None)
    else:
        session.link_transports[bouquet] = transport
    logm.console.log(f"🔗 link to {bouquet}: transport {transport or session.link_transport}")
    return jsonify({"status": "ok", "link_transports": session.link_transports})

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
    from pybiscus.core.gui_events import gui_log_patterns, metric_key_protocol
    from pybiscus.session.agent.agent_weblog import agent_state_protocol
    return render_template("pybiscus/manager.html", manager_port=pybiscus.session.manager.session_manager.manager_port,
                           session_token=pybiscus.session.manager.session_manager.session_token,
                           bouquet=pybiscus.session.manager.session_manager.bouquet,
                           bouquet_color=pybiscus.session.manager.session_manager.bouquet_color,
                           flower_port=pybiscus.session.manager.session_manager.proposed_flower_port(),
                           gui_log_patterns=gui_log_patterns(), agent_state_protocol=agent_state_protocol(),
                           metric_key_protocol=metric_key_protocol())

# **************************

# ************************
# *** Agent management ***
# ************************

agent_feed = Feed()

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

    agent_feed.append({'source': source, 'message': message, 'state': state, 'time': time.time()})

    started = data.get('started')
    if isinstance(started, dict) and ":" in source:
        bouquet, name = source.split(":", 1)
        pybiscus.session.manager.session_manager.started_agents[name] = {
            "url": started.get("url") if is_web_url(started.get("url")) else None,
            "role": started.get("role"), "bouquet": bouquet, "time": time.time()}

    # the source is "<bouquet>:<agent name>", as the page reads it (checkAgentLogs)
    if state and ":" in source:
        pybiscus.session.manager.session_manager.agent_states[source.split(":", 1)[1]] = state

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/agents_logs', methods=['GET'])
def pybiscus_manager_get_agents():
    return jsonify(agent_feed.read(request.args.get("since", 0, type=int)))

# *******************************
# *** Pybiscus Log management ***
# *******************************

log_feed = Feed()
REPORTING_PATH = re.compile(gui_log_patterns()["reporting_path"])

# **************************

@pybiscus_manager_app.route('/webhook/logs', methods=['POST'])
@session_access
def pybiscus_manager_receive_log():
    data = request.json
    message = data.get('content', '')
    source = data.get('source', 'unknown')

    # the time it was received: the page computes the session's duration from it
    log_feed.append({'source': source, 'message': message, 'time': time.time()})
    cycles.note_server_line(message)
    recording = pybiscus.session.manager.session_manager.recording
    if recording is not None:
        reports = REPORTING_PATH.search(message)
        if reports:
            recording.note_reports(reports.group(1))

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/logs', methods=['GET'])
def pybiscus_manager_get_logs():
    return jsonify(log_feed.read(request.args.get("since", 0, type=int)))

# ***********************************
# *** Pybiscus Metrics management ***
# ***********************************

metrics_feed = Feed()

# **************************

@pybiscus_manager_app.route('/webhook/metrics', methods=['POST'])
@session_access
def pybiscus_manager_receive_metrics():
    data = request.json
    metrics = data.get('metrics', '')
    source = data.get('source', 'unknown')
    # message: the raw view; metrics: the table, which decodes the keys
    log = { 'source' : source, 'message' : str(metrics), 'metrics' : metrics if isinstance(metrics, dict) else {} }

    metrics_feed.append(log)

    return jsonify({"status": "success"}), 200

# **************************

@pybiscus_manager_app.route('/pybiscus-session/metrics', methods=['GET'])
def pybiscus_manager_get_metrics():
    return jsonify(metrics_feed.read(request.args.get("since", 0, type=int)))

# *************************************
# *** Pybiscus vignettes management ***
# *************************************

vignettes_feed = Feed()

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

    # they name the file: numbers only
    try:
        metadata = json.loads(request.form["metadata"])
        col_row = f"{int(metadata['col'])}_{int(metadata['row'])}"
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "metadata with an integer col and row is required"}), 400

    # save file
    save_path = os.path.join(vignettes_dir(), f"grid_{col_row}.png")
    os.makedirs(vignettes_dir(), exist_ok=True)
    file.save(save_path)

    vignettes_feed.append(col_row)

    return jsonify({
        "status": "ok",
        "filename": file.filename,
        "metadata": metadata
    })

# **************************

@pybiscus_manager_app.route('/pybiscus-session/vignettes', methods=['GET'])
def pybiscus_manager_get_new_vignettes():
    return jsonify(vignettes_feed.read(request.args.get("since", 0, type=int)))

# *****************************
# *** Session reset support ***
# *****************************

def clear_message_buffers():
    """Vide tout ce qu'un agent ou un run a pu déposer, pour repartir d'une page vierge."""

    for feed in (agent_feed, log_feed, metrics_feed, vignettes_feed):
        feed.clear()

    # les png du run précédent sont un cache d'affichage : l'original est archivé
    # dans experiments/<session>. Sans ce ménage ils survivent jusqu'à être écrasés,
    # et une session plus courte laisserait voir les vignettes de la précédente.
    for vignette in glob.glob(os.path.join(vignettes_dir(), "grid_*.png")):
        try:
            os.remove(vignette)
        except OSError as e:
            logm.console.log(f"vignette removal failed: {vignette} ({e})")
