
class NullMetricsLogger:
    def __init__(self, log_dir):
        self.log_dir = log_dir

    def log_metrics(self, metrics, step=None):
        pass

class MultipleMetricsLogger( ):

    def __init__(self, log_dir, metrics_loggers):
        self.metrics_loggers = metrics_loggers
        self.log_dir = log_dir

    def log_metrics(self, metrics, step=None):
        for metrics_logger in self.metrics_loggers:
            metrics_logger.log_metrics(metrics, step)
