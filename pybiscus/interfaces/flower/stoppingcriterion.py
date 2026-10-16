from typing import TYPE_CHECKING, Optional

# for the annotations only: sessionlink raises EndSession and is imported by the session manager,
# which does not load flwr
if TYPE_CHECKING:
    from flwr.server.history import History


class EndSession(Exception):
    """raised by a strategy before a round starts (configure_fit, initialize_parameters): the session
    ends after the previous round, the exception's message being the reason"""


class StoppingCriterion:

    def start(self) -> None:
        """called when the first round begins: the clients may have been awaited long before"""

    def should_stop(self, server_round: int, history: "History") -> Optional[str]:
        """the reason to end the session after this round, None to go on"""
        return None
