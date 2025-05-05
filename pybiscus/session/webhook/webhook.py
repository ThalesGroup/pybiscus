from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["POST"])
def webhook_root():
    print("Reçu sur / :", request.json)
    return "OK", 200

@app.route("/log_metrics", methods=["POST"])
def webhook_metrics():
    print("Reçu sur /log_metrics :", request.json)
    return "OK", 200

if __name__ == "__main__":
    app.run(port=9999)
