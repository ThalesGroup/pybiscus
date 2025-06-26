
from pybiscus.core.logger.richlogger.richloggerfactory import ConfigRichLoggerFactory, ConfigRichLoggerFactoryData, RichLoggerFactory

# this logger should not be changed
# as it is used in interactive mode with Progress
interactiveConsole = RichLoggerFactory( ConfigRichLoggerFactory( name="rich", config=ConfigRichLoggerFactoryData() ).config ).get_logger()

# this logger may be overwritten according to configuration
console = interactiveConsole
