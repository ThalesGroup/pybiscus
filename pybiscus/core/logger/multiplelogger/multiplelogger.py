
class NullLogger:

    def log(self, *msgs):
        pass

class MultipleLogger( ):

    def __init__(self, loggers):
        self.loggers = loggers

    def log(self, *msgs):
        for logger in self.loggers:
            logger.log(*msgs)
