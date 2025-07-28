import requests

class WebHookLogger:

    def __init__(self, webhook_url, logger_id):
        """
        Initialise the logger with the webhook URL and the logger unique id.
        
        :param webhook_url: webhook URL used to send messages
        :param logger_id: unique id to add into payload as 'source'
        """
        self.webhook_url = webhook_url
        self.logger_id = logger_id

    def log(self, *msgs):
        """
        Send a log message to the webhook, add the 'source' field to the payload
        
        :param msgs: messages to log, they are concatenated before sending
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

    logger.log("Log message", " multi-part", 123)
    logger.log("A simple log message")
