import os
import signal
import timeit
from logging import INFO
from typing import Optional

import flwr as fl
from flwr.common.logger import log
from flwr.server.history import History

import pybiscus.core.pybiscus_logger as logm

# SIGINT/SIGTERM/SIGQUIT are taken by Flower's immediate shutdown; Windows has no SIGUSR1
STOP_SIGNAL = getattr(signal, "SIGUSR1", None)


class StoppableServer(fl.server.Server):

    def __init__(self, *, client_manager: fl.server.ClientManager, strategy: fl.server.strategy.Strategy) -> None:
        super().__init__(client_manager=client_manager, strategy=strategy)
        self.stop_reason: Optional[str] = None
        self.rounds_done = 0
        self.current_round = 0

    def request_stop(self, reason: str) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
            end = f"after round {self.current_round}" if self.current_round else "before its first round"
            logm.console.log(f"🛑 stop requested ({reason}): the session ends {end}")

    def stop_on_signal(self) -> None:
        if STOP_SIGNAL is not None:
            signal.signal(STOP_SIGNAL, lambda _signum, _frame: self.request_stop("manual stop, signal SIGUSR1"))
            logm.console.log(f"🛑 kill -USR1 {os.getpid()} stops the session after the current round")

    # Copy of flwr 1.27 Server.fit, whose `for` over range(num_rounds) cannot be left otherwise:
    # compare with flwr/server/server.py at each upgrade of flwr
    def fit(self, num_rounds: int, timeout: Optional[float]) -> tuple[History, float]:
        history = History()

        log(INFO, "[INIT]")
        self.parameters = self._get_initial_parameters(server_round=0, timeout=timeout)
        log(INFO, "Starting evaluation of initial global parameters")
        res = self.strategy.evaluate(0, parameters=self.parameters)
        if res is not None:
            log(INFO, "initial parameters (loss, other metrics): %s, %s", res[0], res[1])
            history.add_loss_centralized(server_round=0, loss=res[0])
            history.add_metrics_centralized(server_round=0, metrics=res[1])
        else:
            log(INFO, "Evaluation returned no results (`None`)")

        start_time = timeit.default_timer()

        for current_round in range(1, num_rounds + 1):
            # a stop received during the previous round's evaluation, or before the first one
            if self.stop_reason is not None:
                break
            self.current_round = current_round
            self._run_round(current_round, timeout, history, start_time)
            self.rounds_done = current_round

        if self.stop_reason is None:
            logm.console.log(f"🏁 session ended after {self.rounds_done}/{num_rounds} rounds")
        else:
            logm.console.log(f"🛑 session stopped after {self.rounds_done}/{num_rounds} rounds: {self.stop_reason}")

        return history, timeit.default_timer() - start_time

    def _run_round(self, current_round: int, timeout: Optional[float], history: History, start_time: float) -> None:
        log(INFO, "")
        log(INFO, "[ROUND %s]", current_round)
        res_fit = self.fit_round(server_round=current_round, timeout=timeout)
        if res_fit is not None:
            parameters_prime, fit_metrics, _ = res_fit
            if parameters_prime:
                self.parameters = parameters_prime
            history.add_metrics_distributed_fit(server_round=current_round, metrics=fit_metrics)

        res_cen = self.strategy.evaluate(current_round, parameters=self.parameters)
        if res_cen is not None:
            loss_cen, metrics_cen = res_cen
            log(INFO, "fit progress: (%s, %s, %s, %s)",
                current_round, loss_cen, metrics_cen, timeit.default_timer() - start_time)
            history.add_loss_centralized(server_round=current_round, loss=loss_cen)
            history.add_metrics_centralized(server_round=current_round, metrics=metrics_cen)

        res_fed = self.evaluate_round(server_round=current_round, timeout=timeout)
        if res_fed is not None:
            loss_fed, evaluate_metrics_fed, _ = res_fed
            if loss_fed is not None:
                history.add_loss_distributed(server_round=current_round, loss=loss_fed)
                history.add_metrics_distributed(server_round=current_round, metrics=evaluate_metrics_fed)
