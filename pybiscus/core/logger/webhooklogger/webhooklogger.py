import requests

class WebHookLogger:

    def __init__(self, webhook_url, logger_id):
        """
        Initialise le logger avec l'URL du webhook et l'identifiant unique du logger.
        
        :param webhook_url: URL du webhook pour envoyer les messages
        :param logger_id: Identifiant unique à ajouter dans la payload sous 'source'
        """
        self.webhook_url = webhook_url
        self.logger_id = logger_id

    def log(self, *msgs):
        """
        Envoie un message de log au webhook en ajoutant un champ 'source' à la payload.
        
        :param msgs: Messages à loguer, qui seront concaténés et envoyés
        """
        # create the message to be sent
        message = " ".join(str(msg) for msg in msgs)
        
        # create the payload with the id the field 'source'
        payload = {
            'content': message,
            'source': self.logger_id
        }
        
        try:
            # send the message to the webhook using a POST request
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()  # check error in case of error status

            print("✅ Log Webhook call success : ", payload)

        except requests.Timeout:
            print("❌ Log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"❌ Log Webhook HTTP error : {response.status_code} – {http_err}")

        except requests.exceptions.RequestException as err:
            print(f"❌ Log Webhook Other error : {err}")



if __name__ == "__main__":
    webhook_url = 'http://localhost:5555//webhook/logs'
    logger_id = 'Logger123'
    logger = WebHookLogger(webhook_url, logger_id)

    logger.log("C'est un message de log", "avec plusieurs parties", 123)
    logger.log("Un autre message de log")
