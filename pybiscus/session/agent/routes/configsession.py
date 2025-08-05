
from flask import jsonify, render_template, request
from pybiscus.session.agent.pybiscus_agent import reset_registration, reset_session, rest_server
import pybiscus.session.agent.pybiscus_agent as pybagent

client_registration_resume = ""

# ..........................................................
# ........... GET /session/agent/registration/waiting .....
# ..........................................................    

@rest_server.route('/session/agent/registration/waiting')
def session_registration_waiting():

    manager_url = pybagent.registration_parameters['manager_url']
    role        = pybagent.registration_parameters['role']

    return render_template( 'session_agent_waiting.html',
                           state = 'Connecting to session',
                           action = 'Registration',
                           explanation = 'Your agent is waiting to be accepted and registered in the FL session.',
                           callback = f'''

        function sendServerURL(serverURL) {{
        
            const data = {{
                server_url: serverURL
            }};

            fetch('/server-url', {{
                method: 'POST',
                headers: {{
                'Content-Type': 'application/json'
                }},
                body: JSON.stringify(data)
            }})
            .then(response => {{
                if (!response.ok) {{
                    throw new Error(`HTTP error ${{response.status}}`);
                }}
                return response.json();
            }})
            .then(result => {{
                console.log('✅ sendServerURL: Agent response :', result);
            }})
            .catch(error => {{
                console.error('❌ sendServerURL: Agent error :', error);
            }});
        }}
                                   
        function pollSessionParams(interval = 2000) {{
            fetch('{manager_url}/pybiscus-session/params')
                .then(res => {{
                    if (!res.ok) {{
                        return res.json().then(err => {{
                            console.warn("⏳ /pybiscus-session/params : " + err.message);
                            throw new Error(err.message);
                        }});
                    }}
                    return res.json();
                }})
                .then(data => {{
                    console.log("✅ Received session params :", data);

                    if( data.status === "success" ) {{
                        const role = "{role}";
                        console.log("role is ", role);

                        sendServerURL(data.server_url);

                        const query = new URLSearchParams({{ presets: JSON.stringify(data.presets) }}).toString();
                        console.log("query = ", query);
                        const role_url = `/${{role}}/config?${{query}}`;
                        console.log("role_url = ", role_url);
                        
                        window.location.href = role_url;
                        
                    }}
                    else {{
                        setTimeout(() => pollSessionParams(interval), interval);
                    }}
                }})
                .catch(err => {{
                    setTimeout(() => pollSessionParams(interval), interval);
                }});
        }}

        pollSessionParams(2000);

''' )

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

    if the_json:

        pybagent.registration_parameters = the_json

        return jsonify({"status": "ok"})
    
    else:
        return jsonify({"status": "ko"}), 400

