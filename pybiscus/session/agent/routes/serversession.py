
import importlib
import json
from flask import Response, jsonify, request
import urllib
import os

from pybiscus.core.ensure_filesystem import ensure_file_dir_exists
from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
from pybiscus.plugin.registries.data_registry import DataConfig, datamodule_registry
from pybiscus.plugin.registries.model_registry import ModelConfig
from pybiscus.session.agent.ConfigSession import make_session_model
from pybiscus.session.agent.pybiscus_agent import rest_server
from pathlib import Path
import pybiscus.core.pybiscus_logger as logm
from pybiscus.session.auth import session_access
import pybiscus.session.agent.pybiscus_agent as pybagent

# the form's state (options, list items, values), replayed on a freshly generated page: the
# former HTML snapshot froze the interface injected by the scripts, which then got it twice.
# One per agent port: two server agents started from one directory replaced each other's pin
PIN_DIR = ".pybiscus-cache/html-config"
FORMER_PIN = os.path.join(PIN_DIR, "server-pin.json")


def server_pin_path() -> str:
    return os.path.join(PIN_DIR, f"server-pin-{pybagent.agent_port}.json")


def pin_to_read():
    """this agent's pin, else the former shared one, read until this agent pins its own"""
    for path in (server_pin_path(), FORMER_PIN):
        if os.path.isfile(path):
            return path
    return None

# ..........................................................
# .... HEAD /server/config/pin .............................
# ..........................................................
# called by server front-end to check if a configuration is pinned
# (used to show a graphical indicator)
# ..........................................................

@rest_server.route('/server/config/pin', methods=['HEAD', 'GET'])
def check_pinned_config():

    if pin_to_read():

        return Response(status=200)
    else:
        return Response(status=404)

# ..........................................................
# .... POST /server/config/pin .............................
# ..........................................................
# called by server front-end to pin the form's current state (pin button)
# ..........................................................

@rest_server.route('/server/config/pin', methods=['POST'])
def pinConfig():
    state = (request.get_json(silent=True) or {}).get("state")
    if not isinstance(state, dict):
        return {"status": "error", "message": "a 'state' object is required"}, 400

    os.makedirs(PIN_DIR, exist_ok=True)
    with open(server_pin_path(), "w", encoding="utf-8") as f:
        json.dump(state, f)
    return {"status": "ok"}

# ..........................................................
# .... DELETE /server/config/pin ...........................
# ..........................................................
# called by server front-end to forget the pinned configuration (blank button)
# ..........................................................

@rest_server.route('/server/config/pin', methods=['DELETE'])
def deletePinnedConfig():

    try:
        os.remove(server_pin_path())
        return {"status": "deleted"}, 200
    except FileNotFoundError:
        return {"status": "not found"}, 404
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# -----------------------------

def pinned_config_js() -> str:

    path = pin_to_read()
    if path is None:
        return ""

    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        logm.console.log(f"server: pinned configuration ignored, unreadable: {e}")
        return ""

    logm.console.log("server: pinned configuration restored")
    # "</" would end the page's <script> element if a value contained "</script>"
    state_js = json.dumps(state).replace("</", "<\\/")
    return f"\n    pybiscusPinnedState.restore({state_js});\n"

# ..........................................................
# .... GET /server/config ..................................
# ..........................................................
# called by server front-end to get the configuration HTML page, generated, with the pinned
# configuration replayed if there is one, then the session presets
# ..........................................................

@rest_server.route("/server/config", methods=["GET"])
def serverConfigDownload():
    """get the server parameters form"""

    presets_raw = request.args.get("presets")

    from pybiscus.session.agent.pybiscus_agent import PRESETS
    
    if presets_raw:
        try:
            # decode and parse JSON param
            decoded = urllib.parse.unquote(presets_raw)

            session_parameters = json.loads(decoded)

            presets_js = PRESETS(generate_param_js(session_parameters))

            logm.console.log("server: received session parameters: ", session_parameters)
            # logm.console.log("generated params :\n", presets_js)

        except Exception as e:
            logm.console.log( f"/server/config with bad param {str(e)}" )
            raise e
    else:
        logm.console.log("/server/config with no param")

        presets_js = PRESETS("    console.log(\"generate_model_page() called from HTTP GET @ /server/config\" );\n")

    #                      -----------------

    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("show_server_items.js").open('r') as file:
        show_server_items = file.read()

    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("fold_fieldset.js").open('r') as file:
        fold_fieldsets = file.read()

    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("lists_management.js").open('r') as file:
        lists_management = file.read()

    # after the lists' default items (the pinned lists replace them), before the session presets
    # (which override and lock)
    js_code = show_server_items + fold_fieldsets + lists_management + pinned_config_js() + presets_js

    return generate_model_page(ConfigServer,'pybiscus.session.agent.front_end','agent.html','check_exec_buttons', js_code,
                               identity=pybagent.agent_identity())

# ..........................................................
# .... POST /server/config .................................
# ..........................................................
# called by server front-end to store the pybiscus yaml configuration
# for a further execution
# ..........................................................

@rest_server.route("/server/config", methods=["POST"])
def serverConfigUpload():
    """post a server configuration file whose validity is checked"""

    if not saveConfigFromRequest( request ) :
        return jsonify({"serverConfig": "none"})

    try:
        return checkConfigurationFile( "server", pybagent.uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# .... GET /server .........................................
# ..........................................................
# called by server front-end to run pybiscus in server mode
# ..........................................................

@rest_server.route("/server", methods=["POST"])
def server():
    """run in server mode using the uploaded configuration"""

    try:
        # supress storage path as it can be an old one
        import shutil
        from pybiscus.commands.apps_common import client_configs_dir
        shutil.rmtree(client_configs_dir(), ignore_errors=True)

        return interpretConfigurationFile( "server", pybagent.uploaded_file_path )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# .... GET /session/config .................................
# ..........................................................
# called by supervision to establish session common parameters
# ..........................................................

@rest_server.route("/session/config", methods=["GET"])
@session_access
def sessionConfigDownload():
    """get the session parameters form
    the button calls the /server/config?param={json} service
    in order to get a customized server config
    """

    # reset_session()
    
    data_names   = list(datamodule_registry().keys())

    config_session = make_session_model(ModelConfig(), data_names, DataConfig() )

    # the session of a lower level: the model and the data set and locked to the upper level's
    presets_raw = request.args.get("presets")
    from pybiscus.session.agent.pybiscus_agent import PRESETS
    presets_js = PRESETS(generate_param_js(json.loads(urllib.parse.unquote(presets_raw)))) if presets_raw else ""

    # no list in the session form today; a plugin's model holding one would get a ➕📝 doing nothing
    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("lists_management.js").open('r') as file:
        lists_management = file.read()

    return generate_model_page(config_session,'pybiscus.session.agent.front_end','agent.html','launch_session_button', lists_management + presets_js,
                               identity=pybagent.agent_identity())
