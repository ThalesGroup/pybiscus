import requests
from requests.exceptions import RequestException, Timeout

# ------------------------

class PrintAgentLogger():

    def log_agent(self, msg):
        print(msg)

agent_logger = PrintAgentLogger()

# ------------------------

class WebHookAgentLogger():

    def __init__(self, webhook_url, logger_bouquet, logger_id):
        self.webhook_url = webhook_url

        if logger_bouquet is None or logger_bouquet == "":
            self.logger_id = logger_id
        else:
            self.logger_id = f"{logger_bouquet}:{logger_id}"

    def log(self, msg):
        
        try:
            msg = { 'source' : self.logger_id, 'content' : msg }

            response = requests.post(self.webhook_url, json=msg, timeout=5)
            response.raise_for_status()  # raise an exception upon codes 4xx/5xx

            print("✅ Agent log Webhook call success")

        except Timeout:
            print("❌ Agent log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"❌ Agent log Webhook HTTP error : {response.status_code} – {http_err}")

        except RequestException as err:
            print(f"❌ Agent log Webhook Other error : {err}")

def initAgentLogger( webhook_url, logger_bouquet, logger_id ):
    global agent_logger
    agent_logger = WebHookAgentLogger( webhook_url, logger_bouquet, logger_id )
