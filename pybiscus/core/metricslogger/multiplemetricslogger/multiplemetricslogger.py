
class NullMetricsLogger:

    def log_metrics(self, metrics, step=None):
        pass

class MultipleMetricsLogger( ):

    def __init__(self, metrics_loggers):
        self.metrics_loggers = metrics_loggers

    def log_metrics(self, metrics, step=None):
        for metrics_logger in self.metrics_loggers:
            metrics_logger.log_metrics(metrics, step)
