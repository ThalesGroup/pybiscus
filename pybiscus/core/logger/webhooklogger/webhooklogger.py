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
        # Créer le message à envoyer
        message = " ".join(str(msg) for msg in msgs)
        
        # Créer la payload avec l'identifiant dans le champ 'source'
        payload = {
            'content': message,
            'source': self.logger_id  # Ajouter le champ 'source' avec l'identifiant du logger
        }
        
        try:
            # Envoyer le message au webhook via une requête POST
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()  # Vérifie si la requête a échoué

            print("✅ Log Webhook call success : ", payload)

        except requests.Timeout:
            print("❌ Log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"❌ Log Webhook HTTP error : {response.status_code} – {http_err}")

        except requests.exceptions.RequestException as err:
            print(f"❌ Log Webhook Other error : {err}")



# Exemple d'utilisation
if __name__ == "__main__":
    webhook_url = 'http://localhost:5555//webhook/logs'
    logger_id = 'Logger123'  # Identifiant unique pour ce logger
    logger = WebHookLogger(webhook_url, logger_id)

    # Utilisation du logger pour envoyer des messages
    logger.log("C'est un message de log", "avec plusieurs parties", 123)
    logger.log("Un autre message de log")
