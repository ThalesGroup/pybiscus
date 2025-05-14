
from pybiscus.core.logger.multiplelogger.multiplelogger import MultipleLogger, NullLogger
from pybiscus.interfaces.core.logger import LoggerFactory


class MultipleLoggerFactory(LoggerFactory):

    def __init__(self, factories):
        super().__init__()
        self.factories = factories

    def get_logger(self):

        loggers = [ factory.get_logger() for factory in self.factories ]

        nb_loggers = len(loggers)

        if  nb_loggers < 1:
            return NullLogger()

        if nb_loggers == 1:
            return loggers[0]
         
        return MultipleLogger( loggers )
