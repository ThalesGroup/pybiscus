
import importlib
import json
from flask import Response, jsonify, request
import urllib
import os

from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
from pybiscus.plugin.registries import DataConfig, ModelConfig, datamodule_registry, model_registry
from pybiscus.session.agent.ConfigSession import make_session_model
from pybiscus.session.agent.pybiscus_agent import generate_new_cid, reset_session, rest_server
from pathlib import Path
from pybiscus.commands.app_server import ensure_file_dir_exists
import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.agent.pybiscus_agent as pybagent

server_cache_path = ".pybiscus-cache/html-config/server.html"

# ..........................................................
# .... HEAD /server/config/html ............................
# ..........................................................
# called by server front-end to check if an html config is cached
# (used to show a graphical indicator)
# ..........................................................

@rest_server.route('/server/config/html', methods=['HEAD', 'GET'])
def check_html_cache():

    if os.path.isfile(server_cache_path):

        return Response(status=200)
    else:
        return Response(status=404)

# ..........................................................
# .... POST /server/config/html ............................
# ..........................................................
# called by server front-end to cache its current html (pin button)
# ..........................................................

@rest_server.route('/server/config/html', methods=['POST'])
def pinConfigHtml():
    data = request.get_json()
    html = data.get("html", "")

    with open(server_cache_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"status": "ok"}

# ..........................................................
# .... DELETE /server/config/html ..........................
# ..........................................................
# called by server front-end to delete the html cache (blank button)
# ..........................................................

@rest_server.route('/server/config/html', methods=['DELETE'])
def deleteConfigHtml():

    try:
        os.remove(server_cache_path)
        return {"status": "deleted"}, 200
    except FileNotFoundError:
        return {"status": "not found"}, 404
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# -----------------------------

def serverConfigHtmlFromCache():

    if os.path.exists(server_cache_path):
        with open(server_cache_path, encoding="utf-8") as f:
            contenu_html = f.read()

        return contenu_html
    
    return None

# ..........................................................
# .... GET /server/config ..................................
# ..........................................................
# called by server front-end to get the configuration HTML page
# by default the cached one if there is one (with saved customizations)
# otherwise the dynamically generated one (vanilla)
# ..........................................................

@rest_server.route("/server/config", methods=["GET"])
def serverConfigDownload():
    """get the server parameters form
    an optional "param" of type json customizes the html :
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

    #                      -----------------

    cachedConfig = serverConfigHtmlFromCache()

    if cachedConfig is not None:
        logm.console.log("server: configuration read from cache")
        return cachedConfig
    else:
        logm.console.log("server: configuration generated")
    
    #                      -----------------

    param_js = "console.log(\"generate_model_page() called from HTTP GET @ /server/config\" );"

    param_raw = request.args.get("param")
    
    if param_raw:
        try:
            # decode and parse JSON param
            decoded = urllib.parse.unquote(param_raw)

            # store them into context
            pybagent.session_parameters = json.loads(decoded)

            param_js = generate_param_js(pybagent.session_parameters)

            logm.console.log("server: received session parameters: ", pybagent.session_parameters)
            # logm.console.log("generated params :\n", param_js)

        except Exception as e:
            logm.console.log( f"/server/config with bad param {str(e)}" )
            raise e

    else:
        logm.console.log("/server/config with no param")

    with importlib.resources.files("pybiscus.session.agent").joinpath("show_server_items.js").open('r') as file:
        show_server_items = file.read()

    with importlib.resources.files("pybiscus.session.agent").joinpath("fold_fieldset.js").open('r') as file:
        fold_fieldsets = file.read()

    with importlib.resources.files("pybiscus.session.agent").joinpath("lists_management.js").open('r') as file:
        lists_management = file.read()

    js_code = show_server_items + fold_fieldsets + lists_management + param_js

    return generate_model_page(ConfigServer,'pybiscus.session.agent','agent.html','check_exec_buttons', js_code)

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

    return generate_model_page(config_session,'pybiscus.session.agent','agent.html','launch_session_button')

# ..........................................................
# ............. GET /session/parameters/check ..............
# ..........................................................    
# called by client to obtain its set of run parameters
# ..........................................................    

@rest_server.route('/session/parameters/check')
def check_parameters():

    if pybagent.session_parameters:

        client_params = pybagent.session_parameters.copy()
        client_params["values_set"]["client_run.cid"] = generate_new_cid();
        client_params["values_lock"] += [ "client_run.cid" ]    

        return jsonify({"ready": True, "params": client_params})
    else:
        return jsonify({"ready": False})

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
