

import importlib
import json
from flask import jsonify, request
import urllib

from pybiscus.flower_config.config_client import ConfigClient
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
import pybiscus.session.agent.pybiscus_agent as pybagent
from pybiscus.session.agent.presets import list_defaults_js
import pybiscus.core.pybiscus_logger as logm
from pybiscus.session.auth import headers_for
 
# ..........................................................
# .... GET /client/config ..................................
# ..........................................................
# called by client front-end to get the configuration HTML page
# always a dynamically generated one (vanilla)
# ..........................................................

@rest_server.route("/client/config", methods=["GET"])
def clientConfigDownload():
    """get the client parameters form"""

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

        presets_js = PRESETS("    console.log(\"generate_model_page() called from HTTP GET @ /client/config\" );\n")

    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("fold_fieldset.js").open('r') as file:
        fold_fieldsets = file.read()

    # without it, the ➕📝 of the client's lists (a dataset's engines...) did nothing
    with importlib.resources.files("pybiscus.session.agent.front_end").joinpath("lists_management.js").open('r') as file:
        lists_management = list_defaults_js() + file.read()

    # before the session presets, which may fill the lists
    return generate_model_page(ConfigClient,'pybiscus.session.agent.front_end','agent.html','check_exec_buttons', fold_fieldsets + lists_management + presets_js,
                               identity=pybagent.agent_identity())

# ..........................................................
# .... POST /client/config .................................
# ..........................................................
# called by client front-end to store the pybiscus yaml configuration
# for a further execution
# ..........................................................

@rest_server.route("/client/config", methods=["POST"])
def clientConfigUpload():
    """post a client configuration file whose validity is checked"""

    if not saveConfigFromRequest( request ) :
        return jsonify({"serverConfig": "none"})

    try:
        return checkConfigurationFile( "client", pybagent.uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# .... GET /client .........................................
# ..........................................................
# called by client front-end to run pybiscus in client mode
# ..........................................................

@rest_server.route("/client", methods=["POST"])
def client():
    """run in client mode using the uploaded configuration"""

    if pybagent.session_server_url is None:
        logm.console.log("session is not initialized !!!")        
        return jsonify({"error": "session is not initialized" }), 500

    try:

        # kept in the server run's reports: the manager passes it on to the server agent
        send_runconfig(pybagent.uploaded_file_path)
    
        return interpretConfigurationFile( "client", str(pybagent.uploaded_file_path) )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def send_runconfig(yaml_file) -> None:
    import requests
    from pybiscus.session.manager.orders import CALL_TOKEN_HEADER
    manager_url = (pybagent.registration_parameters.get("manager_url") or "").rstrip("/")
    name = pybagent.registration_parameters.get("name")
    if not manager_url or not name:
        logm.console.log("⚠️ the run config is not kept in the server's reports: this agent is registered with no manager")
        return
    url = f"{manager_url}/pybiscus-session/runconfig"
    try:
        with open(yaml_file, encoding="utf-8") as file:
            text = file.read()
        response = requests.post(url, params={"agent": name}, json={"yaml": text}, timeout=10,
                                 headers={**headers_for(url), CALL_TOKEN_HEADER: pybagent.call_token})
        response.raise_for_status()
    except (OSError, requests.RequestException) as error:
        # the run goes on: only the server's reports miss this client's configuration
        logm.console.log(f"⚠️ the run config was not sent to the manager for the server's reports: {error}")
