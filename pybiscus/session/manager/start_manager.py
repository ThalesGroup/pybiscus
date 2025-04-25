import argparse
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)

# global variable that contains the application context
registered_clients = {}
server_url = None
manager_port = None

MAIN_TEMPLATE="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>FL Manager</title>
    <style>
        .split-container {
            display: flex;
            height: 75vh;
            width: 100%;
        }
          .left, .right {
            flex: 1;
            box-sizing: border-box;
        }
        iframe {
            width: 100%;
            height: 100%;
            //border: none;
            border: 1px solid #ccc;
            box-sizing: border-box;
        }

        .container-center {
            display: flex;
            justify-content: center;
        }

        header {
            width: 100%;
            height: 60px;
            background-color: #4a90e2;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 60px;
            background-color: #4a90e2;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        .stack {
            display: flex;
            flex-direction: column;
            gap: 0.5rem; /* espace entre le label et l’iframe */
            margin: auto;
        }
        .right {
        display: flex;
        flex-direction: column;
        }

        .right p {
        margin: 1rem;
        font-size: 1rem;
        }

        .right div {
        flex: 1;
        border-top: 1px solid #ccc;
        background-color: #f0f0f0;
        padding: 1rem;
        box-sizing: border-box;
        }
    </style>
</head>
<body>
    <header>
        <div class="container-center">
            <h1>🧠 Federated Learning Manager</h1>
        </div>
    </header>
    
    <div class="split-container">
        <div class="left">
            <iframe src="/visualize"></iframe>
        </div>
        <div class="right">
            <p>Pybiscus Server Agent URL: <strong>{{ server_url }}</strong></p>
            <iframe src="{{server_url}}/session/config"></iframe>
        </div>
    </div>

    <footer>
        <div class="container-center">
            <button onclick="spreadSessionParams()">📡 Spread session params</button>
        </div>
    </footer>

</body>
</html>
"""

VISUALIZE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Manager Dashboard</title>
    <style>
        canvas { border: 1px solid #ccc; background: #f9f9f9; }
        body { font-family: Arial, sans-serif; text-align: center; margin: 40px; }
        button { margin-top: 20px; padding: 10px 20px; font-size: 16px; }
    </style>
</head>
<body>
    <canvas id="graph" width="600" height="400"></canvas><br>

    <script>
        const canvas = document.getElementById('graph');
        const ctx = canvas.getContext('2d');

        function drawGraph(clients) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;

            const angleStep = (2 * Math.PI) / clients.length;

            clients.forEach((client, i) => {
                const angle = i * angleStep;
                const radius = 120;
                const x = centerX + radius * Math.cos(angle);
                const y = centerY + radius * Math.sin(angle);

                // Line to server
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(x, y);
                ctx.stroke();
            });

            // Draw server
            ctx.beginPath();
            ctx.arc(centerX, centerY, 30, 0, 2 * Math.PI);
            ctx.fillStyle = "blue";
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "white";
            ctx.font = "12px Arial";
            ctx.textAlign = "center";
            ctx.fillText("Server", centerX, centerY + 4);

            clients.forEach((client, i) => {
                const angle = i * angleStep;
                const radius = 120;
                const x = centerX + radius * Math.cos(angle);
                const y = centerY + radius * Math.sin(angle);

                // Draw client
                ctx.beginPath();
                ctx.arc(x, y, 20, 0, 2 * Math.PI);
                ctx.fillStyle = "lightgray";
                ctx.fill();
                ctx.stroke();

                ctx.fillStyle = "black";
                ctx.fillText(client, x, y + 30);
            });
        }

        function updateGraph() {
            fetch('/clients')
                .then(res => res.json())
                .then(data => {
                    const clients = Object.keys(data.clients);
                    drawGraph(clients);
                });
        }

        function spreadSessionParams() {

            /*
            fetch('/ping-server')
                .then(res => res.json())
                .then(data => alert("Server says: " + data.message))
                .catch(err => alert("Error contacting server"));
                */

            fetch('/clients')
                .then(res => res.json())
                .then(data => {
                    const clients = Object.keys(data.clients);
                    alert("Spreading session params to " + clients);
                });
            
        }

        setInterval(updateGraph, 2000);  // Refresh every 2 seconds
        updateGraph();
    </script>
</body>
</html>
"""

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    client_url = data.get("client_url")

    if name and client_url:

        if name in registered_clients:
            
            if registered_clients[name] == client_url:
                return jsonify({
                    "status": "success",
                    "message": f"Client '{name}' already registered.",
                    "server" : server_url,
                    # "registered_clients": list(registered_clients.keys())
                })

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Client '{name}' already registered with a different URL.",
                    # "registered_clients": list(registered_clients.keys())
                })

        registered_clients[name] = client_url

        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
            "server" : server_url,
            # "registered_clients": list(registered_clients.keys())
        })
    else:
        return jsonify({"status": "error", "message": "Missing 'name' or 'client_url'"}), 400

@app.route("/clients", methods=["GET"])
def list_clients():
    return jsonify({"clients": registered_clients})

# sub-view URL
# visualize a graph of session participants
@app.route("/visualize")
def visualize():
    return render_template_string(VISUALIZE_TEMPLATE, server_url=server_url)

# manager main URL
# double view on :
# - session content ( server + connected clients )
# - ConfigSession ( cnx to Pybiscus server )
@app.route("/manage")
def manage():
    return render_template_string(MAIN_TEMPLATE, server_url=server_url)

@app.route("/ping-server")
def ping_server():
    try:
        res = requests.get(server_url)
        return jsonify({"message": res.text})
    except Exception as e:
        return jsonify({"message": f"Error contacting server: {e}"}), 500

def main():
    global server_url
    global manager_port

    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=6000, help="Port to run the manager on")
    parser.add_argument("--server-url", type=str, required=True, help="URL of the central server (e.g. http://localhost:5000)")
    args = parser.parse_args()

    server_url = args.server_url
    manager_port=args.port

    print(f"🚀 Manager starting on port {manager_port}, connected to server: {server_url}")
    app.run(port=manager_port)

if __name__ == "__main__":
    main()
