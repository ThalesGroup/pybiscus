import logging

from flwr.common.logger import LOGGER_NAME

# Pybiscus runs on Flower's legacy API on purpose (start_server, start_client): their deprecation
# warning, repeated at every launch, asked for a migration the operator cannot make. Only these
# two are hidden: a deprecation of anything else Pybiscus calls must stay visible
LEGACY_ENTRY_POINTS = ("flwr.server.start_server()", "flwr.client.start_client()")


class LegacyEntryPointWarningFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.WARNING:
            return True
        message = record.getMessage()
        return not (message.startswith("DEPRECATED FEATURE:")
                    and any(f"{entry_point} is deprecated" in message for entry_point in LEGACY_ENTRY_POINTS))


def hide_legacy_entry_point_warnings() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(f, LegacyEntryPointWarningFilter) for f in logger.filters):
        logger.addFilter(LegacyEntryPointWarningFilter())
