
from pybiscus.core.logger.richlogger.richloggerfactory import ConfigRichLoggerFactory, ConfigRichLoggerFactoryData, RichLoggerFactory

# this logger should not be changed
# as it is used in interactive mode with Progress
interactiveConsole = RichLoggerFactory( ).get_logger()

# this logger may be overwritten according to configuration
console = interactiveConsole
