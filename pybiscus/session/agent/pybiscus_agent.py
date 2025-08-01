import sys
import importlib
from flask import Flask, jsonify, request
from flask_cors import CORS

from rich import print as rich_print
from pathlib import Path
import click
import sys
import os
import subprocess

import argparse

from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.tuples2yaml import parse_tuples_to_yaml_string
from pybiscus.core.pybiscusexception import PybiscusInternalException, PybiscusValueException
from pybiscus.session.agent import agent_weblog

rest_server = Flask(__name__)

#TODO: CORS origin is *
CORS(rest_server, origins="*")
#CORS(rest_server, origins=["http://localhost:5001"])

uploaded_file_path = None

#######################################
########## Session context ############
#######################################

# server part
server_session_client_id_counter = 0

#  common part
registration_parameters = {}
session_parameters = {}

#  client part
session_server_url  = None

# server specific
def generate_new_cid():
    global server_session_client_id_counter
    server_session_client_id_counter += 1
    return str(server_session_client_id_counter)

def reset_registration():

    print("Reset registration !!!")

    global registration_parameters
    registration_parameters = {}

def reset_session():

    print("Reset session !!!")

    global session_parameters
    session_parameters = {}
    global server_session_client_id_counter
    server_session_client_id_counter = 0
    global session_server_url
    session_server_url = None

#######################################
#######################################

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
            
            agent_weblog.agent_logger.log("Invalid configuration !")

            raise PybiscusValueException(f"Invalid configuration")

        lines.append(line)

    # catch complete output at the end of process (incompatible with line by line output read)
    #stdout, stderr = process.communicate()

    return_code = process.wait()

    if return_code == 0:
        agent_weblog.agent_logger.log("Process has finished.")
    else:
        agent_weblog.agent_logger.log(f"Processus {command} has failed with code {return_code}")

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

#  YAML files storage path
UPLOAD_FOLDER = "configs/uploaded/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # directory creation if required

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
            
            agent_weblog.agent_logger.log("checking yaml file")

            output = run_typer_command( ["uv", "run", "pybiscus", mode, "check", file_path ] )
        else:
            raise PybiscusValueException( f"Invalid mode : {mode} (should be server or client)" )

        validation_error_index = output.find("Validation error")

        if validation_error_index != -1:

            agent_weblog.agent_logger.log("Validation error !")

            validation_error = output[validation_error_index:]
            return jsonify({"error": validation_error}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    agent_weblog.agent_logger.log("yaml file checked successfully")
    return jsonify({mode: "yaml file checked successfully"}), 200


def interpretConfigurationFile( mode: str, file_path: str ):

    try:            
        if not Path(file_path).is_file():
            raise PybiscusInternalException( f"Config file not found : {file_path}" )

        if mode == "server" or mode == "client":

            agent_weblog.agent_logger.log(f"launching pybiscus {mode}")

            output = run_typer_command( ["uv", "run", "pybiscus", mode, "launch", file_path ] )
        else:
            raise PybiscusInternalException( f"Invalid mode : {mode} (should be server or client)" )

        validation_error_index = output.find("Validation error")

        if validation_error_index != -1:

            agent_weblog.agent_logger.log("Validation error !")

            validation_error = output[validation_error_index:]
            return jsonify({"error": validation_error}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    agent_weblog.agent_logger.log("pybiscus run completed")
    return jsonify({mode: "pybiscus run completed"}), 200


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

def parse_args():
    """Parse command-line arguments for configuration and port."""
    parser = argparse.ArgumentParser(description="Start Pybiscus-Agent.")
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help="Listening port (default: 5000)"
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help="Path to the YAML configuration file"
    )
    return parser.parse_args()

def main():
    """Main entry point for launching the Flask server."""
    args = parse_args()

    # Store the config path in the Flask app config (accessible via current_app.config)
    rest_server.config['CONFIG_PATH'] = args.config

    if args.config is not None:

        try:
            import yaml
            with open(args.config, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)

                from pybiscus.session.agent.agent_weblog import initAgentLogger

                initAgentLogger( f'{config["manager_url"]}/webhook/agents', config["bouquet"], config["agent_name"] )

        except Exception as e:
            print(f"YAML config loading error : {e}")

    agent_weblog.agent_logger.log(f"Starting Pybiscus-Agent on port {args.port}")

    if args.config is None:
        print(f"Using no configuration file")
    else:
        print(f"Using configuration file: {args.config}")

    rest_server.run(debug=True, host='0.0.0.0', port=args.port)

if __name__ == "__main__":
    main()
