
from flask import render_template, request
import yaml

from pybiscus.session.agent.pybiscus_agent import reset_session, rest_server

registration_resume = ""

# ..........................................................
# .......... GET /mixedsession/agent/registration ..........
# ..........................................................    

@rest_server.route('/mixedsession/agent/registration', methods=['GET'])
def mixed_session_agent_registration():

    reset_session()

    default_config = {
        'manager_url': 'http://localhost:5555',
        'agent_name': 'John Doe',
        'agent_url': 'http://localhost:5001',
        'bouquet': 'noname-cluster',
        'location': 'somewhere',
        'geo_location': {
            'type': 'text',  # 'text' or 'coordinates'
            'text': 'somewhere',
            'latitude': 0.0,
            'longitude': 0.0
        },
        'organisation': 'not-an-organisation',
        'role': 'client'
    }

    # load YAML configuration file
    if 'CONFIG_PATH' in rest_server.config:

        config_path = rest_server.config['CONFIG_PATH']
    
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)

        except FileNotFoundError:
            # Default values
            config = default_config
        except yaml.YAMLError as e:
            print(f"YAML loading error : {e}")
            config = default_config
    else:
        config = default_config

    global registration_resume
    registration_resume = f"{config['role']} {config['agent_name']}@{config['organisation']} in {config['bouquet']}"

    return render_template('mixed_session_agent_registration.html', config=config)

# ..........................................................
# .......... GET /mixedsession/agent/manager_polling ........
# ..........................................................    

@rest_server.route('/mixedsession/agent/parameters/manager_polling')
def mixed_session_agent_parameters_manager_polling():

    manager_url = request.args.get('managerUrl')
    agent_name = request.args.get('agentName')

    # global session_server_url

#     callback_template = """

#     async function check() {
#         const res = await fetch('""" + session_server_url + """/session/server/parameters/check');
#         const data = await res.json();
#         if (data.ready) {
#             console.log("Session parameters are available !");
            
#             fetch('/session/client/parameters', {
#                 method: 'POST',
#                 headers: {
#                     'Content-Type': 'application/json'
#                 },
#                 body: JSON.stringify(data.params)
#             })
#             .then(response => response.json())
#             .then(data => {
#                 console.log("Server response :", data);
#                 window.location.href = "/client/config";
#             })
#             .catch(error => {
#                 console.error("POST error: ", error);
#             });
#         } else {
#             setTimeout(check, 1000);
#         }
#     }

#     check();

# """

    global registration_resume

    return render_template('session_client_waiting.html',
                       state='Pending registration by Session Manager',
                       action=registration_resume,
                       explanation='Your agent is waiting to be accepted in the FL session parameters.',
                    #    callback=callback_template
                       )
