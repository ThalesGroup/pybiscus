import argparse
from flask import Flask
from flask_cors import CORS

# **************************

pybiscus_manager_app = Flask(__name__)
CORS(pybiscus_manager_app, origins="*")

# **************************

# global variable that contains the application context
registered_clients = {}
server_url = None
manager_port = None

# **************************

def main():

    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=5555, help="Port to run the manager on")
    parser.add_argument("--server-url", type=str, required=True, help="URL of the central server (e.g. http://localhost:5555)")
    args = parser.parse_args()

    # memo url server in order to be able to send it to connecting clients
    global server_url
    server_url = args.server_url

    global manager_port
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}, connected to server: {server_url}")
    pybiscus_manager_app.run(port=manager_port)

# **************************

if __name__ == "__main__":
    main()
