from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["POST"])
def webhook_root():
    print("Reçu sur / :", request.json)
    return "OK", 200

@app.route("/webhook/log_metrics", methods=["POST"])
def webhook_metrics():
    print("Reçu sur /webhook/log_metrics :", request.json)
    return "OK", 200

if __name__ == "__main__":
    app.run(port=9999)
