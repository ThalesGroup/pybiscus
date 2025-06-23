
import importlib
import json
from flask import Flask, jsonify, render_template, request, render_template_string, send_from_directory
from flask_cors import CORS

from rich import print as rich_print
from pathlib import Path
import click
import sys
import os
import subprocess

import urllib

from pybiscus.commands.app_server import ensure_file_dir_exists
from pybiscus.pydantic2xxx.pydantic2html import generate_field_html_by_name, generate_model_page
from pybiscus.session.agent.ConfigSession import make_session_model
from pybiscus.session.agent.tuples2yaml import parse_tuples_to_yaml_string
from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.flower_config.config_client import ConfigClient
from pybiscus.core.pybiscusexception import PybiscusInternalException, PybiscusValueException
import pybiscus.core.pybiscus_logger as logm
from pybiscus.plugin.registries import datamodule_registry, model_registry, DataConfig, ModelConfig

rest_server = Flask(__name__)

#TODO: CORS origin is *
CORS(rest_server, origins="*")
#CORS(rest_server, origins=["http://localhost:5001"])

session_parameters = {}
session_client_id_counter = 0
session_server_url = None
session_manager_url = None
session_client_name = None

def generate_new_cid():
    global session_client_id_counter
    session_client_id_counter += 1
    return str(session_client_id_counter)

def reset_session():

    print("Reset session !!!")

    global session_parameters
    session_parameters = {}
    global session_client_id_counter
    session_client_id_counter = 0
    global session_server_url
    session_server_url = None
    global session_manager_url
    session_manager_url = None
    global session_client_name
    session_client_name = None

def shutdown_server():
    """Arrête proprement le serveur Flask."""
    print("############################")
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        #raise RuntimeError("Impossible d'arrêter le serveur. Es-tu en mode debug ?")
        print("## 1")
        sys.exit(0)
        print("## 2")
        sys.exit("Forced server stop !")
        print("## 3")
        pid = os.getpid()
        os.kill(pid,9)
    else:
        print("## 0")
        func()

def run_typer_command(command: list[str]) -> str:

    # run the Typer script as a subprocess
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1 )

    lines = []

    # RT reading of stdout
    for line in process.stdout:

        rich_print(line, end="")  # on screen printing

        line = click.unstyle(line)
        #print(f"##### {line} ####")

        validation_error_index = line.find("This is not a valid config!")

        if validation_error_index != -1:
            raise PybiscusValueException(f"Invalid configuration")

        lines.append(line)

    # catch complete output at the end of process (incompatible with line by line output read)
    #stdout, stderr = process.communicate()

    return_code = process.wait()

    if return_code == 0:
        logm.console.log("Process has finished successfully.")
    else:
        logm.console.log(f"Processus {command} has failed with code {return_code}")
        raise PybiscusInternalException(f"Processus {command} has failed with code {return_code}")

    return ''.join(lines)

# ..........................................................
# .... GET /exit ...........................................
# ..........................................................

@rest_server.route("/exit", methods=["GET"])
def exitFlask():
    sys.exit(0)

# ..........................................................
# .... GET /shutdown .......................................
# ..........................................................

@rest_server.route("/shutdown", methods=["GET"])
def shutdown():
    shutdown_server()
    return "Server shut down."

# ..........................................................
# .... GET /session/config .................................
# ..........................................................

@rest_server.route("/session/config", methods=["GET"])
def sessionConfigDownload():
    """get the session parameters form
    the button calls the /server/config?param={json} service
    in order to get a customized server config
    """

    reset_session()
    
    models_names = list(model_registry().keys())
    data_names = list(datamodule_registry().keys())

    config_session = make_session_model(models_names, ModelConfig(), data_names, DataConfig() )

    return generate_model_page(config_session,'pybiscus.session.agent','agent.html','launch_session_button')

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
            global session_parameters
            session_parameters = json.loads(decoded)

            param_js = generate_param_js(session_parameters)

            logm.console.log("server: received session parameters: ", session_parameters)
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
        global uploaded_file_path
        return checkConfigurationFile( "server", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    if session_parameters:

            param_js = generate_param_js(session_parameters)

            logm.console.log("client: downloaded parameters: ", session_parameters)

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
        global uploaded_file_path
        return checkConfigurationFile( "client", uploaded_file_path )
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

        return interpretConfigurationFile( "server", uploaded_file_path )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# .... GET /client .........................................
# ..........................................................

@rest_server.route("/client", methods=["GET"])
def client():
    """run in client mode using the uploaded configuration"""

    try:
        global session_server_url
        global session_client_name
        global uploaded_file_path

        # upload the client configuration yaml file to the server
        # which is in charge of storing it into the session context
        server_url = f"{session_server_url}/session/log/client/{session_client_name}/runconfig"
        send_yaml_file(uploaded_file_path, server_url)
    
        return interpretConfigurationFile( "client", str(uploaded_file_path) )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#  YAML files storage path
UPLOAD_FOLDER = "configs/uploaded/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # directory creation if required

uploaded_file_path = None

def saveConfigFromRequest( request ) -> bool:

    if "file" not in request.files:
        return False

    file = request.files["file"]

    # check YAML extension
    if not file.filename.endswith((".yaml", ".yml")):
        return False

    # define storage path
    global uploaded_file_path
    #print(file.filename)
    #print(os.path.basename(file.filename))
    uploaded_file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename) )
    
    # save the yaml file
    file.save(uploaded_file_path)

    return True

def checkConfigurationFile( mode: str, file_path: str ):

    try:            
        if not Path(file_path).is_file():
            raise PybiscusInternalException( f"Config file not found : {file_path}" )

        if mode == "server" or mode == "client":
            output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", mode, "check", file_path ] )
        else:
            raise PybiscusValueException( f"Invalid mode : {mode} (should be server or client)" )

        validation_error_index = output.find("Validation error")

        if validation_error_index != -1:
            validation_error = output[validation_error_index:]
            return jsonify({"error": validation_error}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({mode: "yaml file checked successfully"}), 200

def interpretConfigurationFile( mode: str, file_path: str ):

    try:            
        if not Path(file_path).is_file():
            raise PybiscusInternalException( f"Config file not found : {file_path}" )

        if mode == "server" or mode == "client":
            output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", mode, "launch", file_path ] )
        else:
            raise PybiscusInternalException( f"Invalid mode : {mode} (should be server or client)" )

        validation_error_index = output.find("Validation error")

        if validation_error_index != -1:
            validation_error = output[validation_error_index:]
            return jsonify({"error": validation_error}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({mode: "yaml file interpreted successfully"}), 200


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
# ............ POST /config/json/to_yaml ...................
# ..........................................................

@rest_server.route("/config/json/to_yaml", methods=["POST"])
def convert_json_to_yaml():

    try:
        # get JSON payload
        data = request.get_json()

        # chech data format
        if isinstance(data, list) and all(isinstance(sublist, list) for sublist in data):

            tuples = list(map(tuple,data))

            print( tuples )

            yaml_string = parse_tuples_to_yaml_string( tuples )

            print( yaml_string )

            return jsonify({"success": yaml_string}), 200

        else:
            return jsonify({"error": "Invalid format, was expecting a list of 3-tuples of strings"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# ............ POST /config/<model_name>/json ..............
# ..........................................................

@rest_server.route("/config/<model_name>/json", methods=["POST"])
def upload_json(model_name: str):

    try:
        # get JSON payload
        data = request.get_json()

        # chech data format
        if isinstance(data, list) and all(isinstance(sublist, list) for sublist in data):

            tuples = list(map(tuple,data))

            # print( tuples )

            yaml_string = parse_tuples_to_yaml_string( tuples )

            # print( yaml_string )

            # define storage path
            global uploaded_file_path
            uploaded_file_path = os.path.join(UPLOAD_FOLDER, f"{model_name}.yml")
            with open(uploaded_file_path, "w", encoding="utf-8") as file:
                file.write(yaml_string) 

            if model_name == "ConfigServer":
                mode = "server"
            elif model_name == "ConfigClient":
                mode = "client"
            else:
                raise PybiscusInternalException( f"Invalid model name : {model_name}" )

            return checkConfigurationFile( mode, uploaded_file_path )
        else:
            return jsonify({"error": "Invalid format, was expecting a list of 3-tuples of strings"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ..........................................................
# ............ POST /config ................................
# ..........................................................

@rest_server.route("/config", methods=["POST"])
def upload_yaml():
    if "file" not in request.files:
        return jsonify({"error": "no file sent"}), 400

    file = request.files["file"]

    # check YAML extension
    if not file.filename.endswith((".yaml", ".yml")):
        return jsonify({"error": "Bad file format: yaml file required"}), 400

    # define storage path
    global uploaded_file_path
    print(file.filename)
    print(os.path.basename(file.filename))
    uploaded_file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename) )
    
    # save the yaml file
    file.save(uploaded_file_path)

    return jsonify({"message": "yaml file received", "path": uploaded_file_path})


def generate_param_js(payload):
    """generates the js source that matches json-described action to perform
    ie: set selected options by label, lock options so they can not be changed

    {
        "options_set": {
            "model" : "Cifar 10",
            "data" : "Cifar 10"
        },

        "options_lock": [ "model", "data" ],

        "values_set": {
            "client_run.cid" : "17"
        },

        "values_lock": [ "client_run.cid" ]
    }
    """

    options_set = payload.get("options_set", {})
    options_lock = payload.get("options_lock", [])

    prefixes = list(options_set.keys())
    prefixes_str = ", ".join(f'"{key}"' for key in prefixes)

    new_option_items = ", ".join(f"'{key}' : '{value}'" for key, value in options_set.items())
    option_lock_lines = "\n".join(f'lock_option("{opt}");' for opt in options_lock)

    values_set = payload.get("values_set", {})
    values_lock = payload.get("values_lock", [])

    new_values_items = ", ".join(f"'{key}' : '{value}'" for key, value in values_set.items())
    value_lock_lines = "\n".join(f'lock_value("{opt}");' for opt in values_lock)

    param_js = f'''
        const prefixes = [{prefixes_str}];

        /* let selected = selected_options(prefixes);
        console.log("✅ Selected options before :", selected); */

        const new_options = {{ {new_option_items} }}
        set_options( new_options );

        /* selected = selected_options(prefixes);
        console.log("✅ Selected options after :", selected); */

        {option_lock_lines}

        const new_values = {{ {new_values_items} }}
        set_values( new_values );

        {value_lock_lines}
'''.strip()

    return param_js

def store_parameters():
    pass

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

        global session_parameters
        session_parameters = request.json

        print(f"Stored parameters : \n@@@@@@\n{session_parameters}\n@@@@@@")
        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"})

# ..........................................................
# ............. GET /session/server/parameters/check .......
# ..........................................................    

@rest_server.route('/session/server/parameters/check')
def check_parameters():

    if session_parameters:

        client_params = session_parameters.copy()
        client_params["values_set"]["client_run.cid"] = generate_new_cid();
        client_params["values_lock"] += [ "client_run.cid" ]    

        return jsonify({"ready": True, "params": client_params})
    else:
        return jsonify({"ready": False})

# ..........................................................
# ........... GET /session/client/registration/waiting .....
# ..........................................................    

@rest_server.route('/session/client/registration/waiting')
def session_registration_waiting():

    reset_session()

    return render_template( 'session_client_waiting.html',
                           state = 'Connecting to session',
                           action = 'Registration',
                           explanation = 'Your client is waiting to be accepted and registered in the FL session.',
                           callback = '''

        // status check function
        function checkStatus() {
            fetch("/session/client/registration/check")
                .then(res => res.json())
                .then(data => {
                    if (data.redirect) {
                        // Exit animation before redirect
                        document.querySelector('.container').style.animation = 'slideUp 0.5s ease-in reverse';
                        setTimeout(() => {
                            window.location.href = '/session/client/parameters/server_polling';
                        }, 500);
                    }
                })
                .catch(error => {
                    console.error('Error checking status:', error);
                });
        }

        // Check every 2 seconds
        setInterval(checkStatus, 2000);
'''
                           )


# ..........................................................
# ............ GET  /session/client/registration ...........
# ..........................................................    

@rest_server.route('/session/client/registration', methods=['GET'])
def session_registration():

    reset_session()

    return render_template( 'session_client_registration.html',
    )

# ..........................................................
# ............ POST /session/client/registration ...........
# ..........................................................    

@rest_server.route('/session/client/registration', methods=['POST'])
def session_registration_notification():

    the_json = request.json

    if the_json:

        print(f"received notification json : {the_json}")

        global session_manager_url
        session_manager_url = the_json["manager_url"]
        global session_server_url
        session_server_url = the_json["server_url"]
        global session_client_name
        session_client_name = the_json["client_name"]

        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"})

# ..........................................................
# ............. GET /session/client/registration/check .....
# ..........................................................    

@rest_server.route('/session/client/registration/check')
def check_registration():
    return jsonify({'redirect': session_client_name is not None })

# ..........................................................
# ...... GET /session/client/parameters/server_polling .....
# ..........................................................    

@rest_server.route('/session/client/parameters/server_polling')
def session_parameters_waiting():

    global session_server_url

    callback_template = """

    async function check() {
        const res = await fetch('""" + session_server_url + """/session/server/parameters/check');
        const data = await res.json();
        if (data.ready) {
            console.log("Session parameters are available !");
            
            fetch('/session/client/parameters', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data.params)
            })
            .then(response => response.json())
            .then(data => {
                console.log("Server response :", data);
                window.location.href = "/client/config";
            })
            .catch(error => {
                console.error("POST error: ", error);
            });
        } else {
            setTimeout(check, 1000);
        }
    }

    check();

"""

    return render_template('session_client_waiting.html',
                       state='Waiting for session parameters',
                       action='Server request',
                       explanation='Your client is requesting the server to provide the FL session parameters.',
                       callback=callback_template)

# ..........................................................
# ... POST /session/log/client/<client_name>/runconfig .....
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

# ..........................................................
# ............. GET /test/html .....
# ..........................................................    

@rest_server.route('/test/html')
def test_html():

    from pydantic import BaseModel
    from typing import Optional, List
    from pybiscus.flower_config.config_server import ConfigServerOnnxExport, OnnxAxe

    class MyContent(BaseModel):
        #opt_int: Optional[int] # pyright: ignore[reportInvalidTypeForm]
        # onnx_export: ConfigServerOnnxExport
        an_axe: OnnxAxe
        axes: List[OnnxAxe]

    class MyConf(BaseModel):
    
        # loggers: list[LoggerConfig()] # pyright: ignore[reportInvalidTypeForm]
        # strategy: Optional[StrategyConfig()] # pyright: ignore[reportInvalidTypeForm]
        # opt_int: Optional[int] # pyright: ignore[reportInvalidTypeForm]
        content: MyContent
        # label_de_cadix: int = 0

    with importlib.resources.files("pybiscus.session.agent").joinpath("lists_management.js").open('r') as file:
        lists_management = file.read()

    # return generate_field_html_by_name()
    return generate_model_page(MyConf,'pybiscus.session.agent','agent.html','check_exec_buttons', lists_management)

# ..........................................................    

if __name__ == "__main__":

    if len(sys.argv) > 1:
        portNumber = int(sys.argv[1])
    else:
        portNumber = 5000

    rest_server.run(debug=True, host="0.0.0.0", port=portNumber)
