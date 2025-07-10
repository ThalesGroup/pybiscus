
from pathlib import Path
from flask import jsonify, render_template, request
from pybiscus.commands.app_server import ensure_file_dir_exists
from pybiscus.plugin.registries import DataConfig, ModelConfig, datamodule_registry, model_registry
from pybiscus.pydantic2xxx.pydantic2html import generate_model_page
from pybiscus.session.agent.ConfigSession import make_session_model
from pybiscus.session.agent.pybiscus_agent import generate_new_cid, reset_session, rest_server
import pybiscus.session.agent.pybiscus_agent as pybagent

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
# ............. GET /session/server/parameters/check .......
# ..........................................................    

@rest_server.route('/session/server/parameters/check')
def check_parameters():

    if pybagent.session_parameters:

        client_params = pybagent.session_parameters.copy()
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

        pybagent.session_manager_url = the_json["manager_url"]
        pybagent.session_server_url = the_json["server_url"]
        pybagent.session_client_name = the_json["client_name"]

        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"})

# ..........................................................
# ............. GET /session/client/registration/check .....
# ..........................................................    

@rest_server.route('/session/client/registration/check')
def check_registration():
    return jsonify({'redirect': pybagent.session_client_name is not None })

# ..........................................................
# ...... GET /session/client/parameters/server_polling .....
# ..........................................................    

@rest_server.route('/session/client/parameters/server_polling')
def session_parameters_waiting():

    callback_template = """

    async function check() {
        const res = await fetch('""" + pybagent.session_server_url + """/session/server/parameters/check');
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
