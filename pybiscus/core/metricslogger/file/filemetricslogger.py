import logging
from pathlib import Path

from pybiscus.interfaces.core.logger import LoggerFactory

class FileMetricsLoggerFactory(LoggerFactory):

    def __init__(self, log_file_path):
        super().__init__()
        self.log_file_path = Path(log_file_path)

    def get_metricslogger(self,reporting_path):

        return FileMetricsLogger( reporting_path / self.log_file_path )


class FileMetricsLogger():

    def __init__(self, log_file_path):

        if log_file_path is str:
            log_file_path = Path(log_file_path)

        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        metrics_logger = logging.getLogger("metrics")
        metrics_logger.setLevel(logging.INFO)
        metrics_handler = logging.FileHandler(log_file_path)
        metrics_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        metrics_logger.addHandler(metrics_handler)

        self.logging = metrics_logger

    def log_metrics(self, metrics, step=-1):

        if step == -1:
            self.logging.info(metrics)
        else:
            self.logging.info(f"[step {step}] {metrics}")
