import logging
from pathlib import Path

from pybiscus.interfaces.core.logger import LoggerFactory

class FileLoggerFactory(LoggerFactory):

    def __init__(self, log_file_path):
        super().__init__()
        self.log_file_path = log_file_path

    def get_logger(self):

        return FileLogger( self.log_file_path )


class FileLogger():

    def __init__(self, log_file_path):

        if log_file_path is str:
            log_file_path = Path(log_file_path)

        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        info_logger = logging.getLogger("info")
        info_logger.setLevel(logging.INFO)
        info_handler = logging.FileHandler(log_file_path)
        info_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        info_logger.addHandler(info_handler)

        self.logging = info_logger

    def log(self, *msgs):

        # create the message to be logged
        message = " ".join(str(msg) for msg in msgs)

        self.logging.info(message)
