import json
import queue
import socket

from flask import Response, jsonify, render_template, request

import pybiscus.session.agent.pybiscus_agent as pybagent
from pybiscus.session.agent.pybiscus_agent import rest_server
from pybiscus.session.auth import session_access
from pybiscus.session.agent.run_session import run_session

# sans trafic, les proxys et le navigateur peuvent couper une connexion SSE oisive :
# on émet un commentaire de keep-alive à intervalle régulier
SSE_HEARTBEAT_SECONDS = 15

# ..........................................................
# .... GET /run ............................................
# ..........................................................
# progress page the config page switches to once the run is launched
# ..........................................................

@rest_server.route("/run", methods=["GET"])
def runMonitor():
    state = run_session.snapshot()

    registration = pybagent.registration_parameters
    from pybiscus.core.gui_events import gui_log_patterns
    return render_template("run_monitor.html", mode=state["mode"] or "pybiscus",
                           agent_name=registration.get("name"), location=registration.get("location"),
                           gui_log_patterns=gui_log_patterns())

# ..........................................................
# .... GET /run/status .....................................
# ..........................................................

@rest_server.route("/run/status", methods=["GET"])
def runStatus():
    return jsonify(run_session.snapshot())

# ..........................................................
# .... GET /run/events .....................................
# ..........................................................
# server-sent events : full backlog then live log lines
# ..........................................................

@rest_server.route("/run/events", methods=["GET"])
def runEvents():

    def stream():
        subscriber = run_session.subscribe()
        try:
            state = run_session.snapshot()
            yield f"data: {json.dumps({'type': 'snapshot', **state})}\n\n"

            while True:
                try:
                    event = subscriber.get(timeout=SSE_HEARTBEAT_SECONDS)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"
        finally:
            run_session.unsubscribe(subscriber)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ..........................................................
# .... POST /run/stop ......................................
# ..........................................................

# also called by the manager when its session is dropped
@rest_server.route("/run/stop", methods=["POST"])
@session_access
def runStop():
    if run_session.stop():
        return jsonify({"status": "terminating"}), 202

    return jsonify({"status": "no running process"}), 409

# ..........................................................
# .... POST /run/relaunch ..................................
# ..........................................................

# called by the manager at each deadline of a repeated session: the configuration checked and
# launched by the operator the first time, run again
@rest_server.route("/run/relaunch", methods=["POST"])
@session_access
def runRelaunch():
    if run_session.relaunch():
        return jsonify({"status": "relaunched", "mode": run_session.mode}), 202

    return jsonify({"status": "no run to launch again, or still running"}), 409

# ..........................................................
# .... GET /run/listening ..................................
# ..........................................................

# called by the manager before it launches the clients of a repeated session again: Flower's
# legacy client does not retry, one started before its server listens fails at once. Probed here,
# on the server's machine: the manager may not reach a server listening on the loopback only.
# Only the port of this agent's server run is probed: any port asked for would tell which services
# listen on this machine's loopback.
@rest_server.route("/run/listening", methods=["GET"])
@session_access
def runListening():
    port = run_session.server_port()
    if port is None:
        return jsonify({"status": "no server run whose port is known"}), 409
    asked = request.args.get("port")
    if asked is not None and asked != str(port):
        return jsonify({"status": f"only the port of this agent's server run is probed ({port})"}), 400
    listening = False
    # localhost may resolve to IPv4 only, and the session form listens on [::1] or [::]
    for loopback in ("::1", "127.0.0.1"):
        try:
            socket.create_connection((loopback, port), timeout=1).close()
            listening = True
            break
        except OSError:
            pass
    return jsonify({"listening": listening, "running": run_session.is_running()})

# ..........................................................
# .... POST /run/stop-after-round ..........................
# ..........................................................

# called by the manager: a server run ends after its current round, its reports written
@rest_server.route("/run/stop-after-round", methods=["POST"])
@session_access
def runStopAfterRound():
    if run_session.stop_after_round():
        return jsonify({"status": "stopping after the current round"}), 202

    return jsonify({"status": "no running server process"}), 409
