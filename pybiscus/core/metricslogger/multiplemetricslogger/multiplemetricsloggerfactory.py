
from pybiscus.core.metricslogger.multiplemetricslogger.multiplemetricslogger import MultipleMetricsLogger, NullMetricsLogger
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


class MultipleMetricsLoggerFactory(MetricsLoggerFactory):

    def __init__(self, log_dir, factories):
        super().__init__()
        self.log_dir=log_dir
        self.factories = factories

    def get_metricslogger(self):

        loggers = [ factory.get_metricslogger() for factory in self.factories ]

        nb_loggers = len(loggers)

        if  nb_loggers < 1:
            return NullMetricsLogger(self.log_dir)

        if nb_loggers == 1:
            return loggers[0]
         
        return MultipleMetricsLogger( self.log_dir, loggers )
