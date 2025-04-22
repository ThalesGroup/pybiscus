from flask import Flask, request, jsonify, redirect, url_for, render_template_string
import threading

app = Flask(__name__)
session_parameters = {}  # Pour l'exemple : une seule session

@app.route('/session')
def session_page():
    return render_template_string("""
        <h1>En attente de démarrage...</h1>
        <p>Veuillez patienter.</p>
        <script>
        async function check() {
            const res = await fetch('/session/check_parameters');
            const data = await res.json();
            if (data.ready) {
                // Rediriger avec les paramètres
                const url = new URL("/launch", window.location.origin);
                for (const [key, value] of Object.entries(data.params)) {
                    url.searchParams.append(key, value);
                }
                window.location.href = url.toString();
            } else {
                setTimeout(check, 1000);
            }
        }
        check();
        </script>
    """)

@app.route('/session/parameters', methods=['POST'])
def set_parameters():
    global session_parameters
    session_parameters = request.json or {}
    return jsonify({"status": "ok"})

@app.route('/session/check_parameters')
def check_parameters():
    if session_parameters:
        return jsonify({"ready": True, "params": session_parameters})
    return jsonify({"ready": False})

@app.route('/launch')
def launch():
    return f"<h1>Lancement de la session avec paramètres :</h1><pre>{dict(request.args)}</pre>"

if __name__ == "__main__":
    app.run(debug=True)
