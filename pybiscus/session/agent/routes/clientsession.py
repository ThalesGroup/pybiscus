

import importlib
from flask import jsonify, request

from pybiscus.flower_config.config_client import ConfigClient
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.pybiscus_agent import checkConfigurationFile, generate_param_js, interpretConfigurationFile, rest_server, saveConfigFromRequest
import pybiscus.session.agent.pybiscus_agent as pybagent
import pybiscus.core.pybiscus_logger as logm
 
# ..........................................................
# .... GET /client/config ..................................
# ..........................................................

@rest_server.route("/client/config", methods=["GET"])
def clientConfigDownload():
    """get the client parameters form
    if the global session_parameters dict is defined :
    - options can be set
    - options can be locked to the active value with change not permitted
    - values can be set
    - values can be locked as the input field is set read only
    """
    param_js = "console.log(\"generate_model_page() called from HTTP GET @ /client/config\" );"

    if pybagent.session_parameters:

            param_js = generate_param_js(pybagent.session_parameters)

            logm.console.log("client: downloaded parameters: ", pybagent.session_parameters)

    with importlib.resources.files("pybiscus.session.agent").joinpath("fold_fieldset.js").open('r') as file:
        fold_fieldsets = file.read()

    return generate_model_page(ConfigClient,'pybiscus.session.agent','agent.html','check_exec_buttons', fold_fieldsets + param_js)

# ..........................................................
# .... POST /client/config .................................
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

@rest_server.route("/client", methods=["GET"])
def client():
    """run in client mode using the uploaded configuration"""

    try:

        # upload the client configuration yaml file to the server
        # which is in charge of storing it into the session context
        server_url = f"{pybagent.session_server_url}/session/log/client/{pybagent.session_client_name}/runconfig"
        send_yaml_file(pybagent.uploaded_file_path, server_url)
    
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

# ..........................................................
# ............ POST /session/client/parameters .............
# ..........................................................

@rest_server.route('/session/client/parameters', methods=['POST'])
def set_parameters():
    """ the client agent front-end after getting access to the session configuration
    send it to the backend by posting it to this URL 
    which stores it into ist context
    """

    if request.json:

        print(f"received json : {request.json}")

        pybagent.session_parameters = request.json

        print(f"Stored parameters : \n@@@@@@\n{pybagent.session_parameters}\n@@@@@@")
        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"})


