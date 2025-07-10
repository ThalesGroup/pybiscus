
import importlib
import json
from flask import jsonify, request
import urllib

from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
import pybiscus.core.pybiscus_logger as logm
import pybiscus.session.agent.pybiscus_agent as pybagent

# ..........................................................
# .... GET /server/config ..................................
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

    with importlib.resources.files("pybiscus.session.agent").joinpath("fold_fieldset.js").open('r') as file:
        fold_fieldsets = file.read()

    with importlib.resources.files("pybiscus.session.agent").joinpath("lists_management.js").open('r') as file:
        lists_management = file.read()

    return generate_model_page(ConfigServer,'pybiscus.session.agent','agent.html','check_exec_buttons', fold_fieldsets + lists_management + param_js)

# ..........................................................
# .... POST /server/config .................................
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

