
from pybiscus.core.logger.richlogger.richloggerfactory import ConfigRichLoggerFactory, ConfigRichLoggerFactoryData, RichLoggerFactory

console = RichLoggerFactory( ConfigRichLoggerFactory( name="rich", config=ConfigRichLoggerFactoryData() ).config ).get_logger()
