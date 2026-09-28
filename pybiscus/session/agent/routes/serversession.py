
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
from pybiscus.plugin.registries.model_registry import ModelConfig, model_registry
from pybiscus.session.agent.ConfigSession import make_session_model
from pybiscus.session.agent.pybiscus_agent import rest_server
from pathlib import Path
import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.agent.pybiscus_agent as pybagent

# the form's state (options, list items, values), replayed on a freshly generated page: the
# former HTML snapshot froze the interface injected by the scripts, which then got it twice
server_pin_path = ".pybiscus-cache/html-config/server-pin.json"

# ..........................................................
# .... HEAD /server/config/pin .............................
# ..........................................................
# called by server front-end to check if a configuration is pinned
# (used to show a graphical indicator)
# ..........................................................

@rest_server.route('/server/config/pin', methods=['HEAD', 'GET'])
def check_pinned_config():

    if os.path.isfile(server_pin_path):

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

    os.makedirs(os.path.dirname(server_pin_path), exist_ok=True)
    with open(server_pin_path, "w", encoding="utf-8") as f:
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
        os.remove(server_pin_path)
        return {"status": "deleted"}, 200
    except FileNotFoundError:
        return {"status": "not found"}, 404
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# -----------------------------

def pinned_config_js() -> str:

    if not os.path.exists(server_pin_path):
        return ""

    try:
        with open(server_pin_path, encoding="utf-8") as f:
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

            # store them into context
            pybagent.session_parameters = json.loads(decoded)

            presets_js = PRESETS(generate_param_js(pybagent.session_parameters))

            logm.console.log("server: received session parameters: ", pybagent.session_parameters)
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

    return generate_model_page(ConfigServer,'pybiscus.session.agent.front_end','agent.html','check_exec_buttons', js_code)

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

@rest_server.route("/server", methods=["GET"])
def server():
    """run in server mode using the uploaded configuration"""

    try:
        # supress storage path as it can be an old one
        import shutil
        shutil.rmtree("./experiments/config_clients", ignore_errors=True)

        return interpretConfigurationFile( "server", pybagent.uploaded_file_path )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# .... GET /session/config .................................
# ..........................................................
# called by supervision to establish session common parameters
# ..........................................................

@rest_server.route("/session/config", methods=["GET"])
def sessionConfigDownload():
    """get the session parameters form
    the button calls the /server/config?param={json} service
    in order to get a customized server config
    """

    # reset_session()
    
    models_names = list(model_registry().keys())
    data_names   = list(datamodule_registry().keys())

    config_session = make_session_model(models_names, ModelConfig(), data_names, DataConfig() )

    return generate_model_page(config_session,'pybiscus.session.agent.front_end','agent.html','launch_session_button')

# ..........................................................
# ... POST /session/log/client/<client_name>/runconfig .....
# ..........................................................
# called by client back-end to store its pybiscus yaml run parameters
# ..........................................................    

@rest_server.route("/session/log/client/<client_name>/runconfig", methods=["POST"])
def log_client_runconfig(client_name: str):
    """ the client agent front-end after setting its run configuration
    send it to the server which stores them
    """

    if "file" not in request.files:
        return jsonify({"error": "no file sent"}), 400

    file = request.files["file"]

    # check YAML extension
    if not file.filename.endswith((".yaml", ".yml")):
        return jsonify({"error": "Bad file format: yaml file required"}), 400

    # define storage path
    file_path = Path(f"experiments/config_clients/{client_name}.yml")

    # create the directory
    ensure_file_dir_exists(file_path)

    file.save(file_path)

    return jsonify({"message": "yaml file received", "path": str(file_path)})
