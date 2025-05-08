
from pybiscus.core.logger.richlogger.richloggerfactory import ConfigRichLoggerFactory, ConfigRichLoggerFactoryData, RichLoggerFactory

pluggable_logger = RichLoggerFactory( ConfigRichLoggerFactory( name="rich", config=ConfigRichLoggerFactoryData() ).config ).get_logger()
