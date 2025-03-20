
from flask import Flask, jsonify, request
from typer_app import app as pybiscus_typer_app
from typer.testing import CliRunner
from rich import print as rich_print
#import click
import sys
import werkzeug
import os

rest_server = Flask(__name__)

def shutdown_server():
    """Arrête proprement le serveur Flask."""
    print("############################")
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        #raise RuntimeError("Impossible d'arrêter le serveur. Es-tu en mode debug ?")
        print("## 1")
        sys.exit(0)
        print("## 2")
        sys.exit("Forced server stop !")
        print("## 3")
        pid = os.getpid()
        os.kill(pid,9)
    else:
        print("## 0")
        func()

#def run_typer_command(command: str, *args) -> str:
def run_typer_command(command: list[str]) -> str:

    if False:

        runner = CliRunner()
        result = runner.invoke(pybiscus_typer_app, [command] + list(args) ) 
        rich_print(result.output)
        return result.output

    else:

        import subprocess

        # Exécuter le script Typer en subprocess
        #process = subprocess.Popen(["./launch/uv/cifar10_cnn/distributed/without_ssl/server.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1 )

        # Lire la sortie en temps réel
        for line in process.stdout:
            rich_print(line, end="")  # Affiche en direct sur l'écran

        # Récupérer la sortie complète
        #stdout, stderr = process.communicate()
        #print("\nSortie complète capturée :", stdout)

        return_code = process.wait() # returncode
        if return_code == 0:
            print("Le processus s'est terminé avec succès.")
        else:
            print(f"Le processus {command} a échoué avec le code {return_code}")

        return ""

@rest_server.route("/exit", methods=["GET"])
def exitFlask():
    sys.exit(0)

@rest_server.route("/shutdown", methods=["GET"])
def shutdown():
    shutdown_server()
    return "Serveur arrêté."

@rest_server.route("/server/config", methods=["POST"])
def serverConfig():

    if not saveConfigFromRequest( request ) :
        return jsonify({"serverConfig": "none"})

    global uploaded_file_path

    output = run_typer_command( ["uv", "run", "python", "src/main.py", "server", "check", uploaded_file_path ] )
    return jsonify({"check": output})

@rest_server.route("/client/config", methods=["POST"])
def clientConfig():

    if not saveConfigFromRequest( request ) :
        return jsonify({"clientConfig": "none"})

    global uploaded_file_path

    output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "check", uploaded_file_path ] )
    return jsonify({"check": output})

@rest_server.route("/server", methods=["GET"])
def server():
    #name = request.args.get("name", "World")
    #output = run_typer_command("server", "launch", "./configs/cifar10_cnn/distributed/without_ssl/server.yml" )
    #output = run_typer_command( ["uv", "run", "python", "src/main.py", "server", "launch", "./configs/cifar10_cnn/distributed/without_ssl/server.yml"] )
    output = run_typer_command( ["uv", "run", "python", "src/main.py", "server", "launch", uploaded_file_path ] )
    #return jsonify({"output": click.unstyle(output)})
    return jsonify({"server": "run performed" })

@rest_server.route("/client/<int:nb>", methods=["GET"])
def client(nb: int):
    #output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", f"./configs/cifar10_cnn/distributed/without_ssl/client_{nb}.yml"] )
    output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", uploaded_file_path ] )
    return jsonify({f"client{nb}": "run performed" })

@rest_server.route("/client1", methods=["GET"])
def client1():
    #output = run_typer_command("client", "launch", "./configs/cifar10_cnn/distributed/without_ssl/client1.yml" )
    output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", "./configs/cifar10_cnn/distributed/without_ssl/client_1.yml"] )
    #output = run_typer_command( ["./launch/uv/cifar10_cnn/distributed/without_ssl/client1.sh"] )
    return jsonify({"output": output})

@rest_server.route("/client2", methods=["GET"])
def client2():
    #output = run_typer_command("client", "launch", "./configs/cifar10_cnn/distributed/without_ssl/client2.yml" )
    #output = run_typer_command("./launch/uv/cifar10_cnn/distributed/without_ssl/client2.sh" )
    #output = run_typer_command( ["uv", "run", "python", "src/main.py", "client", "launch", "./configs/cifar10_cnn/distributed/without_ssl/client_2.yml"] )
    output = run_typer_command( ["./launch/uv/cifar10_cnn/distributed/without_ssl/client2.sh"] )
    return jsonify({"output": output})

#  Répertoire où stocker les fichiers YAML
UPLOAD_FOLDER = "configs/uploaded/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Crée le dossier s'il n'existe pas

uploaded_file_path = None

def saveConfigFromRequest( request ) -> bool:

    if "file" not in request.files:
        return False

    file = request.files["file"]

    # Vérifier que le fichier a une extension YAML
    if not file.filename.endswith((".yaml", ".yml")):
        return False

    # Définir le chemin de stockage
    global uploaded_file_path
    #print(file.filename)
    #print(os.path.basename(file.filename))
    uploaded_file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename) )
    
    # Sauvegarder le fichier
    file.save(uploaded_file_path)

    return True

@rest_server.route("/config", methods=["POST"])
def upload_yaml():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier envoyé"}), 400

    file = request.files["file"]

    # Vérifier que le fichier a une extension YAML
    if not file.filename.endswith((".yaml", ".yml")):
        return jsonify({"error": "Format invalide, uniquement YAML accepté"}), 400

    # Définir le chemin de stockage
    global uploaded_file_path
    print(file.filename)
    print(os.path.basename(file.filename))
    uploaded_file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename) )
    
    # Sauvegarder le fichier
    file.save(uploaded_file_path)

    return jsonify({"message": "Fichier bien reçu", "path": uploaded_file_path})

if __name__ == "__main__":

    if len(sys.argv) > 1:
        portNumber = int(sys.argv[1])
    else:
        portNumber = 5000

    rest_server.run(debug=True, host="0.0.0.0", port=portNumber)

