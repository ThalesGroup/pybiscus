import argparse
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)
registered_clients = {}
server_url = None  # Stocké globalement pour accès dans la route /manage

MAIN_TEMPLATE="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Deux URLs sur une page</title>
    <style>
        .container {
            display: flex;
            height: 100vh;
        }
        iframe {
            flex: 1;
            border: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <iframe src="http://localhost:5555/visualize"></iframe>
        <iframe src="http://localhost:5000/session/config"></iframe>
    </div>
</body>
</html>
"""

TEMPLATE = """
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
    <h1>🧠 Federated Learning Manager</h1>
    <p>Server URL: <strong>{{ server_url }}</strong></p>
    <canvas id="graph" width="600" height="400"></canvas><br>
    <button onclick="spreadSessionParams()">📡 Spread session params</button>
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

# l'envoi de paramètres en python
"""
import requests

url = "http://localhost:5000/session/parameters"
data = {
    "user": "alice",
    "mode": "test",
    "lang": "fr"
}

response = requests.post(url, json=data)

if response.ok:
    print("✅ Paramètres envoyés avec succès :", response.json())
else:
    print("❌ Échec de l'envoi :", response.status_code, response.text)
"""
# l'envoi de paramètres en js
"""
const params = {
    user: "alice",
    mode: "test",
    lang: "fr"
};

fetch("/session/parameters", {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify(params)
})
.then(response => {
    if (!response.ok) {
        throw new Error("Erreur lors de l'envoi des paramètres");
    }
    return response.json();
})
.then(data => {
    console.log("✅ Paramètres envoyés avec succès :", data);
})
.catch(error => {
    console.error("❌ Erreur :", error);
});
"""

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    client_url = data.get("client_url")

    if name and client_url:
        registered_clients[name] = client_url
        return jsonify({
            "status": "success",
            "message": f"Client '{name}' registered.",
            "registered_clients": list(registered_clients.keys())
        })
    else:
        return jsonify({"status": "error", "message": "Missing 'name' or 'client_url'"}), 400

@app.route("/clients", methods=["GET"])
def list_clients():
    return jsonify({"clients": registered_clients})

@app.route("/visualize")
def visualize():
    return render_template_string(TEMPLATE, server_url=server_url)

@app.route("/manage")
def manage():
    return render_template_string(MAIN_TEMPLATE, server_url="http://localhost:5000/session/config", visualize_url="localhost:5555/visualize")

@app.route("/ping-server")
def ping_server():
    try:
        res = requests.get(server_url)
        return jsonify({"message": res.text})
    except Exception as e:
        return jsonify({"message": f"Error contacting server: {e}"}), 500

def main():
    global server_url
    parser = argparse.ArgumentParser(description="Start the Federated Learning Manager Server.")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the manager on")
    parser.add_argument("--server-url", type=str, required=True, help="URL of the central server (e.g. http://localhost:7000)")
    args = parser.parse_args()

    server_url = args.server_url
    print(f"🚀 Manager starting on port {args.port}, connected to server: {server_url}")
    app.run(port=args.port)

if __name__ == "__main__":
    main()
