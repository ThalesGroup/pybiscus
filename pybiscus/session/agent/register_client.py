import argparse
import requests
from flask import Flask
import webbrowser
import threading

def register_client(name: str, client_url: str, manager_url: str):
    endpoint = f"{manager_url}/register"
    payload = {
        "name": name,
        "client_url": client_url
    }

    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        print(f"✅ Client '{name}' successfully registered with the manager.")
        print(f"📡 Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Registration failed: {e}")

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Welcome on client 1 !</h1>"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a client to the FL manager.")
    parser.add_argument("--name", required=True, help="Client name")
    parser.add_argument("--client-url", required=True, help="URL where the client is running (e.g., http://localhost:8080)")
    parser.add_argument("--manager-url", required=True, help="URL of the manager server (e.g., http://localhost:5000)")

    args = parser.parse_args()

    register_client(args.name, args.client_url, args.manager_url)

    def open_browser():
        # webbrowser.open("http://localhost:5001/client/config")
        webbrowser.open("http://localhost:5001/")

    # # Lancer le navigateur dans un thread séparé, pour éviter de bloquer le démarrage du serveur
    # threading.Timer(1.0, open_browser).start()

    # # Lancer Flask
    # app.run(debug=False, port=5001)
