import requests
from requests.exceptions import RequestException, Timeout

# ------------------------

class AgentState:
    """Protocole agent -> session manager.

    Ces valeurs voyagent dans le champ `state` du webhook et pilotent la machine à états
    du manager : ce sont un contrat, pas du texte d'affichage. Le manager les compare
    telles quelles (cf. checkAgentLogs dans manager/templates/pybiscus/manager.html).
    """

    VALIDATING    = "validating"
    VALIDATED     = "validated"
    NOT_VALIDATED = "not validated"
    EXECUTING     = "executing"
    TERMINATED    = "terminated"
    FAILED        = "failed"

# ------------------------

class PrintAgentLogger():

    def log(self, msg, state: str = None):
        if state is None:
            print(msg)
        else:
            print(f"[{state}] {msg}")

agent_logger = PrintAgentLogger()

# ------------------------

class WebHookAgentLogger():

    def __init__(self, webhook_url, logger_bouquet, logger_id):
        self.webhook_url = webhook_url

        if logger_bouquet is None or logger_bouquet == "":
            self.logger_id = logger_id
        else:
            self.logger_id = f"{logger_bouquet}:{logger_id}"

    def log(self, msg, state: str = None):

        try:
            msg = { 'source' : self.logger_id, 'content' : msg }

            if state is not None:
                msg['state'] = state

            response = requests.post(self.webhook_url, json=msg, timeout=5)
            response.raise_for_status()  # raise an exception upon codes 4xx/5xx

            print("✅ Agent log Webhook call success")

        except Timeout:
            print("⚠️ Agent log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"⚠️ Agent log Webhook HTTP error : {response.status_code} – {http_err}")

        except RequestException as err:
            print(f"⚠️ Agent log Webhook Other error : {err}")

def initAgentLogger( webhook_url, logger_bouquet, logger_id ):
    global agent_logger
    agent_logger = WebHookAgentLogger( webhook_url, logger_bouquet, logger_id )
