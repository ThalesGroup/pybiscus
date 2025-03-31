
from flask import Flask, jsonify, request
#from typer.testing import CliRunner
from rich import print as rich_print
from pathlib import Path
import click
import sys
#import werkzeug
import os
import subprocess

from src.node.pydantic2html import generate_model_form
from src.node.tuples2yaml import parse_tuples_to_yaml_string
from src.flower.server_fabric import ConfigServer
from src.flower.client_fabric import ConfigClient
from src.pybiscusexception import PybiscusInternalException, PybiscusValueException
from src.console import console

rest_server = Flask(__name__)

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

@rest_server.route("/server/config", methods=["GET"])
def serverConfigDownload():
    return generate_model_form(ConfigServer)

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
    return generate_model_form(ConfigClient)

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
    #output = run_typer_command( ["uv", "run", "python", "src/main.py", "server", "launch", "./configs/cifar10_cnn/distributed/without_ssl/server.yml"] )
    try:
        #output = run_typer_command( ["uv", "run", "python", "src/main.py", "server", "launch", uploaded_file_path ] )
        return interpretConfigurationFile( "server", uploaded_file_path )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    #return jsonify({"server": "run performed" })

@rest_server.route("/client", methods=["GET"])
def client():
    #output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", f"./configs/cifar10_cnn/distributed/without_ssl/client_{nb}.yml"] )
    try:
        #output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", uploaded_file_path ] )
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
            output = run_typer_command( ["uv", "run", "python", "src/main.py", mode, "check", file_path ] )
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
            output = run_typer_command( ["uv", "run", "python", "src/main.py", mode, "launch", file_path ] )
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

if __name__ == "__main__":

    if len(sys.argv) > 1:
        portNumber = int(sys.argv[1])
    else:
        portNumber = 5000

    rest_server.run(debug=True, host="0.0.0.0", port=portNumber)

