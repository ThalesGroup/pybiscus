

import importlib
import json
from flask import jsonify, request
import urllib

from pybiscus.flower_config.config_client import ConfigClient
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
import pybiscus.session.agent.pybiscus_agent as pybagent
import pybiscus.core.pybiscus_logger as logm
 
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

    return generate_model_page(ConfigClient,'pybiscus.session.agent.front_end','agent.html','check_exec_buttons', fold_fieldsets + presets_js)

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

@rest_server.route("/client", methods=["GET"])
def client():
    """run in client mode using the uploaded configuration"""

    if pybagent.session_server_url is None:
        logm.console.log("session is not initialized !!!")        
        return jsonify({"error": "session is not initialized" }), 500

    try:

        # upload the client configuration yaml file to the server
        # which is in charge of storing it into the session context
        target_url = f"{pybagent.session_server_url}/session/log/client/{pybagent.registration_parameters['name']}/runconfig"
        send_yaml_file(pybagent.uploaded_file_path, target_url)
    
        return interpretConfigurationFile( "client", str(pybagent.uploaded_file_path) )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def send_yaml_file(yaml_file, url, timeout=10):

    import requests
    from requests.exceptions import RequestException, Timeout

    try:
        with open(yaml_file, "rb") as f:
            files = {
                "file": (f.name, f, "application/x-yaml")
            }

            response = requests.post(url, files=files, timeout=timeout)
            response.raise_for_status()

            print("✅ Status:", response.status_code)
            print("📝 Response:", response.text)

    except FileNotFoundError:
        print(f"❌ Fichier introuvable : {yaml_file}")
    except Timeout:
        print(f"⏱️ Timeout après {timeout} secondes")
    except RequestException as e:
        print(f"❌ Erreur HTTP : {e}")
    except Exception as e:
        print(f"❗ Erreur inattendue : {e}")
