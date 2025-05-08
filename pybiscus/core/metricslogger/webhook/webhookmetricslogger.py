import requests
from requests.exceptions import RequestException, Timeout

class WebHookMetricsLogger():

    def __init__(self, root_dir, webhook_url):
        self.log_dir = root_dir
        self.webhook_url = webhook_url

    def log_metrics(self, metrics, step):
        
        try:
            response = requests.post(self.webhook_url, json=metrics, timeout=5)
            response.raise_for_status()  # raise an exception upon codes 4xx/5xx

            print("✅ Metrics log Webhook call success")

        except Timeout:
            print("❌ Metrics log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"❌ Metrics log Webhook HTTP error : {response.status_code} – {http_err}")

        except RequestException as err:
            print(f"❌ Metrics log Webhook Other error : {err}")
