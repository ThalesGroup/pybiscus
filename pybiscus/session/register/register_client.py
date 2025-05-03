import argparse
import requests

def notify_client_node( name: str, client_url: str, manager_url: str, server_url: str ):
    endpoint = f"{client_url}/session/client/registration"
    payload = {
        "client_name": name,
        "manager_url": manager_url,
        "server_url": server_url,
    }

    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        the_json = response.json()
        print(f"📡 Client response: {the_json}")

        if the_json["status"] == "ok":
            print(f"✅ Client '{name}' acked.")

        else:
            print(f'❌ Client nacked')

    except requests.exceptions.RequestException as e:
        print(f"❌ Registration failed: {e}")

def register_client(name: str, client_url: str, manager_url: str):
    endpoint = f"{manager_url}/register"
    payload = {
        "name": name,
        "client_url": client_url
    }

    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        the_json = response.json()
        print(f"📡 Manager response: {the_json}")

        if the_json["status"] == "success":
            print(f"✅ Client '{name}' successfully registered with the manager.")

            notify_client_node( name, client_url, manager_url, the_json["server"] )
        else:
            print(f"❌ Registration failed: {the_json["message"]}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Registration failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a client to the FL manager.")
    parser.add_argument("--name", required=True, help="Client name")
    parser.add_argument("--client-url", required=True, help="URL where the client is running (e.g., http://localhost:5001)")
    parser.add_argument("--manager-url", required=True, help="URL of the manager server (e.g., http://localhost:6000)")

    args = parser.parse_args()

    register_client(args.name, args.client_url, args.manager_url)
