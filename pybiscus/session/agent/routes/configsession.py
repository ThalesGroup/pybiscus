
from flask import jsonify, render_template, request
from pybiscus.session.agent.pybiscus_agent import reset_registration, reset_session, rest_server
import pybiscus.session.agent.pybiscus_agent as pybagent

client_registration_resume = ""

# ..........................................................
# ........... GET /session/agent/registration/waiting .....
# ..........................................................    

@rest_server.route('/session/agent/registration/waiting')
def session_registration_waiting():

    # reset_session()
    print(f"WAITING {pybagent.registration_parameters}")
    print(f"WAITING2 {pybagent.registration_parameters['role']}")

    manager_url = pybagent.registration_parameters['manager_url']
    role        = pybagent.registration_parameters['role']

    return render_template( 'session_agent_waiting.html',
                           state = 'Connecting to session',
                           action = 'Registration',
                           explanation = 'Your agent is waiting to be accepted and registered in the FL session.',
                           callback = f'''
                           
        function pollSessionParams(interval = 2000) {{
            fetch('{manager_url}/pybiscus-session/params')
                .then(res => {{
                    if (!res.ok) {{
                        return res.json().then(err => {{
                            console.warn("⏳ En attente : " + err.message);
                            throw new Error(err.message);
                        }});
                    }}
                    return res.json();
                }})
                .then(data => {{
                    console.log("✅ Session params :", data);

                    if( data.status === "success" ) {{

                        const server_url  = data.server; // TODO: send it to BE
                        console.log("1 server url is : ", server_url);
                        const role    = "{role}";
                        console.log("2 server url is : ", server_url);
                        console.log("role is ", role);
                        console.log("3 server url is : ", server_url);
                        const role_url = `/${{role}}/config`;
                        console.log("4 server url is : ", server_url);
                        console.log("role_url is ", role_url);
                        //const message = data.message;

                        window.location.href = role_url;
                        
                        // Check every 2 seconds
                        //setInterval(checkSessionRun, 2000);
                    }}
                    else {{
                        setTimeout(() => pollSessionParams(interval), interval);
                    }}
                }})
                .catch(err => {{
                    setTimeout(() => pollSessionParams(interval), interval);
                }});
        }}

        pollSessionParams(3000);

''' )

#         // session run check function
#         function checkSessionRun() {
#             fetch("/session/client/registration/check")
#                 .then(res => res.json())
#                 .then(data => {
#                     // Exit animation before redirect
#                     document.querySelector('.container').style.animation = 'slideUp 0.5s ease-in reverse';
#                     setTimeout(() => {
#                         window.location.href = '/session/client/parameters/server_polling';
#                     }, 500);
#                 })
#                 .catch(error => {
#                     console.error('Error checking status:', error);
#                 });
#         }


# ..........................................................
# ............ GET  /session/client/registration ...........
# ..........................................................    

@rest_server.route('/session/agent/registration', methods=['GET'])
def session_registration():

    reset_session()
    reset_registration()

    default_config = {
        'manager_url': 'http://localhost:5555',
        'agent_name': 'John Doe',
        'agent_url': 'http://localhost:5001',
        'bouquet': 'noname-bouquet',
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

        import yaml

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

    global client_registration_resume
    client_registration_resume = f"{config['role']} {config['agent_name']}@{config['organisation']} in {config['bouquet']}"

    return render_template( 'session_agent_registration.html', config=config)

# ..........................................................
# ............ POST /session/agent/registration ...........
# ..........................................................    

@rest_server.route('/session/agent/registration', methods=['POST'])
def session_registration_parameters():

    the_json = request.json

    print(f"REGISTER before {pybagent.registration_parameters}")

    if the_json:

        #TODO: remove comment
        # REGISTERED: {
        #      'name': 'cortaix-labs-00', 
        #      'agent_url': 'http://localhost:5000', 
        #      'bouquet': 'cortaixlabs-cluster', 
        #      'location': 'palaiseau-dc', 
        #      'geo_location': {'latitude': 48.71439, 'longitude': 2.20278}, 
        #      'organisation': 'CortaiX Labs', ''
        #      'role': 'server', 
        #      'manager_url': 'http://localhost:5555'
        #      }
        pybagent.registration_parameters = the_json

        print(f"REGISTER after {pybagent.registration_parameters}")

        #TODO: se server_url n'est pas connu au moment du recording !!!
        # pybagent.session_server_url  = the_json["server_url"]

        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"}), 400

# ..........................................................
# ............. GET /session/client/registration/check .....
# ..........................................................    

#TODO:
# @rest_server.route('/session/client/registration/check')
# def check_registration():
#     return jsonify({'redirect': pybagent.session_client_name is not None })

# ..........................................................
# ...... GET /session/client/parameters/server_polling .....
# ..........................................................    

#TODO: check if used

@rest_server.route('/session/client/parameters/server_polling')
def session_parameters_waiting():

    callback_template = f"""

    async function check() {{
        const res = await fetch('{pybagent.session_server_url}/session/parameters/check');
        const data = await res.json();
        if (data.ready) {{
            console.log("Session parameters are available !");

            fetch('/session/client/parameters', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify(data.params)
            }})
            .then(response => response.json())
            .then(data => {{
                console.log("Server response :", data);
                window.location.href = "/client/config";
            }})
            .catch(error => {{
                console.error("POST error: ", error);
            }});
        }} else {{
            setTimeout(check, 1000);
        }}
    }}

    check();

"""

    return render_template('session_agent_waiting.html',
                       state='Waiting for session parameters',
                       action='Server request',
                       explanation='Your client is requesting the server to provide the FL session parameters.',
                       callback=callback_template)

