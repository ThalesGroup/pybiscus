from typing import Optional

from flwr.server.history import History


class StoppingCriterion:

    def start(self) -> None:
        """called when the first round begins: the clients may have been awaited long before"""

    def should_stop(self, server_round: int, history: History) -> Optional[str]:
        """the reason to end the session after this round, None to go on"""
        return None
