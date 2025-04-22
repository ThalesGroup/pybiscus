
import json
from flask import Flask, jsonify, request, render_template_string

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
session_parameters = {}

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

    # models_names = list(datamodule_registry.keys())
    # data_names = list(model_registry.keys())

    models_names = list(datamodule_registry.keys())
    data_names = list(model_registry.keys())

    config_session = make_session_model(models_names, ModelConfig, data_names, DataConfig)

    return generate_model_page(config_session,'pybiscus.session.node','node.html','launch_session_button')

@rest_server.route("/server/config", methods=["GET"])
def serverConfigDownload():

    param_js = "console.log(generate_model_page() called from HTTP GET @ /server/config );"

    param_raw = request.args.get("param")
    
    if not param_raw:
        console.log("/server/config with no param")
    else:
        try:
            # decode and parse JSON param
            decoded = urllib.parse.unquote(param_raw)
            config = json.loads(decoded)

            param_js = """
                const prefixes = ["model", "data", "ssl"];
                let selected = selected_options(prefixes);
                console.log("✅ Selected options:", selected);

                const new_values = { 'model' : 'Cifar 10', 'data' : 'Cifar 10', 'ssl' : 'None' }
                set_options( new_values );
                    selected = selected_options(prefixes);
                    console.log("✅ Selected options 2:", selected);

                lock_option("ssl");
                lock_option("data");
                lock_option("model");

                selected_options
            """

        except Exception as e:
            console.log( f"/server/config with bad param {str(e)}" )

    return generate_model_page(ConfigServer,'pybiscus.session.node','node.html','check_exec_buttons',param_js)

@rest_server.route("/server/config", methods=["POST"])
def serverConfigUpload():

    if not saveConfigFromRequest( request ) :
        return jsonify({"serverConfig": "none"})

    try:
        global uploaded_file_path
        return checkConfigurationFile( "server", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rest_server.route("/client/config", methods=["GET"])
def clientConfigDownload():
    return generate_model_page(ConfigClient,'pybiscus.session.node','node.html','check_exec_buttons')

@rest_server.route("/client/config", methods=["POST"])
def clientConfigUpload():

    if not saveConfigFromRequest( request ) :
        return jsonify({"serverConfig": "none"})

    try:
        global uploaded_file_path
        return checkConfigurationFile( "client", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rest_server.route("/server", methods=["GET"])
def server():
    #output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", "server", "launch", "./configs/cifar10_cnn/distributed/without_ssl/server.yml"] )
    try:
        #output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", "server", "launch", uploaded_file_path ] )
        return interpretConfigurationFile( "server", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    #return jsonify({"server": "run performed" })

@rest_server.route("/client", methods=["GET"])
def client():
    #output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", "client", "launch", f"./configs/cifar10_cnn/distributed/without_ssl/client_{nb}.yml"] )
    try:
        #output = run_typer_command( ["uv", "run", "python", "pybiscus/main.py", "client", "launch", uploaded_file_path ] )
        return interpretConfigurationFile( "client", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    #return jsonify({f"client": "run performed" })

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

@rest_server.route('/session')
def session_page():
    return render_template_string("""
        <h1>En attente de démarrage...</h1>
        <p>Veuillez patienter.</p>
        <script>
        async function check() {
            const res = await fetch('/session/check_parameters');
            const data = await res.json();
            if (data.ready) {
                // Rediriger avec les paramètres
                const url = new URL("/launch", window.location.origin);
                for (const [key, value] of Object.entries(data.params)) {
                    url.searchParams.append(key, value);
                }
                window.location.href = url.toString();
            } else {
                setTimeout(check, 1000);
            }
        }
        check();
        </script>
    """)

@rest_server.route('/session/parameters', methods=['POST'])
def set_parameters():
    global session_parameters
    session_parameters = request.json or {}
    return jsonify({"status": "ok"})

@rest_server.route('/session/check_parameters')
def check_parameters():
    if session_parameters:
        return jsonify({"ready": True, "params": session_parameters})
    return jsonify({"ready": False})

@rest_server.route('/launch')
def launch():
    return f"<h1>Lancement de la session avec paramètres :</h1><pre>{dict(request.args)}</pre>"

if __name__ == "__main__":

    if len(sys.argv) > 1:
        portNumber = int(sys.argv[1])
    else:
        portNumber = 5000

    rest_server.run(debug=True, host="0.0.0.0", port=portNumber)

