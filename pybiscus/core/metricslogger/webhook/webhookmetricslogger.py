import requests
from requests.exceptions import RequestException, Timeout

class WebHookMetricsLogger():

    def __init__(self, webhook_url, logger_id):
        self.webhook_url = webhook_url
        self.logger_id = logger_id

    def log_metrics(self, metrics, step=-1):
        
        if step is None:
            step = -1

        try:
            _metrics = metrics.copy()
            _metrics['step'] = step
            msg = { 'source' : self.logger_id, 'metrics' : _metrics }

            response = requests.post(self.webhook_url, json=msg, timeout=5)
            response.raise_for_status()  # raise an exception upon codes 4xx/5xx

            print("✅ Metrics log Webhook call success")

        except Timeout:
            print("❌ Metrics log Webhook Failure on timeout")

        except requests.HTTPError as http_err:
            print(f"❌ Metrics log Webhook HTTP error : {response.status_code} – {http_err}")

        except RequestException as err:
            print(f"❌ Metrics log Webhook Other error : {err}")
