import json
import queue

from flask import Response, jsonify, render_template

from pybiscus.session.agent.pybiscus_agent import rest_server
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

    return render_template("run_monitor.html", mode=state["mode"] or "pybiscus")

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

@rest_server.route("/run/stop", methods=["POST"])
def runStop():
    if run_session.stop():
        return jsonify({"status": "terminating"}), 202

    return jsonify({"status": "no running process"}), 409
