
import json
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

from rich import print as rich_print
from pathlib import Path
import click
import sys
import os
import subprocess

import urllib

from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.node.ConfigSession import make_session_model
from pybiscus.session.node.tuples2yaml import parse_tuples_to_yaml_string
from pybiscus.flower.server_fabric import ConfigServer
from pybiscus.flower.client_fabric import ConfigClient
from pybiscus.core.pybiscusexception import PybiscusInternalException, PybiscusValueException
from pybiscus.core.console import console
from pybiscus.core.registries import datamodule_registry, model_registry, DataConfig, ModelConfig

rest_server = Flask(__name__)

#TODO: CORS origin is *
CORS(rest_server, origins="*")
#CORS(rest_server, origins=["http://localhost:5001"])  # autorise ton frontend

session_parameters = {}
session_server_url = None
session_manager_url = None
session_client_name = None

def reset_session():
    global session_parameters
    session_parameters = {}
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
        console.log("Process has finished successfully.")
    else:
        console.log(f"Processus {command} has failed with code {return_code}")
        raise PybiscusInternalException(f"Processus {command} has failed with code {return_code}")

    return ''.join(lines)

@rest_server.route("/exit", methods=["GET"])
def exitFlask():
    sys.exit(0)


@rest_server.route("/shutdown", methods=["GET"])
def shutdown():
    shutdown_server()
    return "Server shut down."


@rest_server.route("/session/config", methods=["GET"])
def sessionConfigDownload():
    """get the session parameters form
    the button calls the /server/config?param={json} service
    in order to get a customized server config
    """
    models_names = list(datamodule_registry.keys())
    data_names = list(model_registry.keys())

    config_session = make_session_model(models_names, ModelConfig, data_names, DataConfig)

    return generate_model_page(config_session,'pybiscus.session.node','node.html','launch_session_button')


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

            console.log("server: received session parameters: ", session_parameters)
            # console.log("generated params :\n", param_js)

        except Exception as e:
            console.log( f"/server/config with bad param {str(e)}" )
            raise e

    else:
        console.log("/server/config with no param")

    return generate_model_page(ConfigServer,'pybiscus.session.node','node.html','check_exec_buttons',param_js)


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

@rest_server.route("/client/config", methods=["GET"])
def clientConfigDownload():
    """get the client parameters form
    if global session_parameters dict is defined :
    - options values can be set
    - options can be locked to the active value with change not permitted
    """
    param_js = "console.log(\"generate_model_page() called from HTTP GET @ /client/config\" );"

    if session_parameters:

            param_js = generate_param_js(session_parameters)

            console.log("client: stored session parameters: ", session_parameters)
            # console.log("generated params :\n", param_js)

    return generate_model_page(ConfigClient,'pybiscus.session.node','node.html','check_exec_buttons', param_js)

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

@rest_server.route("/server", methods=["GET"])
def server():
    """run in server mode using the uploaded configuration"""

    try:
        return interpretConfigurationFile( "server", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rest_server.route("/client", methods=["GET"])
def client():
    """run in client mode using the uploaded configuration"""

    try:
        return interpretConfigurationFile( "client", uploaded_file_path )
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


@rest_server.route("/config/<model_name>/json", methods=["POST"])
def upload_json(model_name: str):

    try:
        # get JSON payload
        data = request.get_json()

        # chech data format
        if isinstance(data, list) and all(isinstance(sublist, list) for sublist in data):

            tuples = list(map(tuple,data))

            print( tuples )

            yaml_string = parse_tuples_to_yaml_string( tuples )

            print( yaml_string )

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
            "ssl" : "None",
        },

        "options_lock": [ "model", "data", "ssl" ]
    }
    """

    options_set = payload.get("options_set", {})
    options_lock = payload.get("options_lock", [])

    prefixes = list(options_set.keys())
    prefixes_str = ", ".join(f'"{key}"' for key in prefixes)

    new_values_items = ", ".join(f"'{key}' : '{value}'" for key, value in options_set.items())

    lock_lines = "\n".join(f'lock_option("{opt}");' for opt in options_lock)

    param_js = f'''
const prefixes = [{prefixes_str}];

let selected = selected_options(prefixes);
console.log("✅ Selected options:", selected);

const new_values = {{ {new_values_items} }}
set_options( new_values );

selected = selected_options(prefixes);
console.log("✅ Selected options 2:", selected);

{lock_lines}
'''.strip()

    return param_js

def store_parameters():
    pass


@rest_server.route('/session/client/parameters', methods=['POST'])
def set_parameters():
    """ the client node front-end after getting access to the session configuration
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
    

@rest_server.route('/session/server/parameters/check')
def check_parameters():

    if session_parameters:
        return jsonify({"ready": True, "params": session_parameters})
    else:
        return jsonify({"ready": False})


@rest_server.route('/session/client/registration/waiting')
def session_registration_waiting():

    # reset_session()

    return render_template_string("""
        <h1>Pybiscus session</h1>
        <p>Waiting to be registered in session</p>

        <script>
            function checkStatus() {
                fetch('/session/client/registration/check')
                    .then(res => res.json())
                    .then(data => {
                        if (data.redirect) {
                            window.location.href = '/session/client/parameters/server_polling';
                        }
                    });
            }

            // Vérifie toutes les 2 secondes
            setInterval(checkStatus, 2000);
        </script>
    """)


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


@rest_server.route('/session/client/registration/check')
def check_registration():
    return jsonify({'redirect': session_client_name is not None })


@rest_server.route('/session/client/parameters/server_polling')
def session_parameters_waiting():

    global session_server_url
    server_url=session_server_url

    return render_template_string("""
        <h1>Pybiscus session</h1>
        <p>Waiting that server sets global configuration parameters</p>

        <script>
        async function check() {
            const res = await fetch('{{server_url}}/session/server/parameters/check');
            const data = await res.json();
            if (data.ready) {
                
                console.log( "Session parameters are available !" );
   
                fetch('/session/client/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data.params)
                })
                .then(response => response.json()) // ou .text() selon ce que le backend retourne
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
        </script>
    """, server_url=server_url)

if __name__ == "__main__":

    if len(sys.argv) > 1:
        portNumber = int(sys.argv[1])
    else:
        portNumber = 5000

    rest_server.run(debug=True, host="0.0.0.0", port=portNumber)
