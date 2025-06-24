
from pybiscus.core.metricslogger.multiplemetricslogger.multiplemetricslogger import MultipleMetricsLogger, NullMetricsLogger
from pybiscus.interfaces.core.metricsloggerfactory import MetricsLoggerFactory


class MultipleMetricsLoggerFactory(MetricsLoggerFactory):

    def __init__(self, factories):
        super().__init__()
        self.factories = factories

    def get_metricslogger(self,reporting_path):

        loggers = [ factory.get_metricslogger(reporting_path) for factory in self.factories ]

        nb_loggers = len(loggers)

        if  nb_loggers < 1:
            return NullMetricsLogger()

        if nb_loggers == 1:
            return loggers[0]
         
        return MultipleMetricsLogger(loggers)
