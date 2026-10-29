import os
import signal
import time
import timeit
from logging import INFO
from typing import Optional, Sequence

import flwr as fl
from flwr.common.logger import log
from flwr.server.history import History

import pybiscus.core.gui_events as gui_events
import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.schedule import Schedule
from pybiscus.core.stop_signal import STOP_SIGNAL
from pybiscus.interfaces.flower.stoppingcriterion import EndSession, StoppingCriterion
from pybiscus.interfaces.flower.strategydecorator import strategy_trains


class StoppableServer(fl.server.Server):

    def __init__(self, *, client_manager: fl.server.ClientManager, strategy: fl.server.strategy.Strategy,
                 criteria: Sequence[StoppingCriterion] = (), schedule: Optional[Schedule] = None,
                 stop_without_new_data: bool = False) -> None:
        super().__init__(client_manager=client_manager, strategy=strategy)
        self.criteria = list(criteria)
        self.schedule = schedule
        self.stop_without_new_data = stop_without_new_data
        self.trains = strategy_trains(strategy)
        self.stop_reason: Optional[str] = None
        self.rounds_done = 0
        self.current_round = 0

    def request_stop(self, reason: str) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
            gui_events.log_stop_requested(reason, self.current_round)

    def stop_on_signal(self) -> None:
        if STOP_SIGNAL is not None:
            signal.signal(STOP_SIGNAL, lambda _signum, _frame: self.request_stop("operator's request (SIGUSR1)"))
            logm.console.log(f"🛑 kill -USR1 {os.getpid()} stops the session after the current round")

    def fit(self, num_rounds: int, timeout: Optional[float]) -> tuple[History, float]:
        try:
            return self._fit(num_rounds, timeout)
        except Exception:
            # Flower disconnects the clients only after a fit that returns: their open streams kept
            # the server's process alive after the exception, and the clients waiting, for ever
            self.disconnect_all_clients(timeout=timeout)
            raise

    # Copy of flwr 1.27 Server.fit, whose `for` over range(num_rounds) cannot be left otherwise:
    # compare with flwr/server/server.py at each upgrade of flwr
    def _fit(self, num_rounds: int, timeout: Optional[float]) -> tuple[History, float]:
        history = History()

        log(INFO, "[INIT]")
        try:
            self.parameters = self._get_initial_parameters(server_round=0, timeout=timeout)
        except EndSession as end:
            self.request_stop(str(end))
            gui_events.log_session_end(0, num_rounds, self.stop_reason)
            return history, 0.0
        log(INFO, "Starting evaluation of initial global parameters")
        res = self.strategy.evaluate(0, parameters=self.parameters)
        if res is not None:
            log(INFO, "initial parameters (loss, other metrics): %s, %s", res[0], res[1])
            history.add_loss_centralized(server_round=0, loss=res[0])
            history.add_metrics_centralized(server_round=0, metrics=res[1])
        else:
            log(INFO, "Evaluation returned no results (`None`)")

        start_time = timeit.default_timer()
        for criterion in self.criteria:
            criterion.start()

        # Flower's round number goes on over the rounds a schedule skips, rounds_done does not
        current_round = 0
        while self.rounds_done < num_rounds:
            # a stop received during the previous round's evaluation, or before the first one
            if self.stop_reason is not None:
                break
            if self.schedule is not None and not self._wait_deadline(current_round, history):
                break
            current_round += 1
            self.current_round = current_round
            gui_events.log_round_start(current_round, self.rounds_done + 1, num_rounds)
            try:
                counted = self._run_round(current_round, timeout, history, start_time)
            except EndSession as end:
                # raised before the round trained anything: the session ends after the previous one
                self.current_round = current_round - 1
                self.request_stop(str(end))
                break
            if counted:
                self.rounds_done += 1
                if self.schedule is not None:
                    gui_events.log_rounds_done(self.rounds_done, num_rounds)
            elif self.stop_without_new_data:
                self.current_round = current_round - 1
                self.request_stop(f"no client had new data in round {current_round}, which does not count")
            else:
                logm.console.log(f"⏭️ round {current_round} skipped: no client {'had new data' if self.trains else 'evaluated'}, "
                                 f"it does not count ({self.rounds_done}/{num_rounds} rounds run)")
            self._test_criteria(current_round, history, clock_only=not counted)

        gui_events.log_session_end(self.rounds_done, num_rounds, self.stop_reason)

        return history, timeit.default_timer() - start_time

    def _wait_deadline(self, last_round: int, history: History) -> bool:
        """False: the session ended while waiting (a stop asked for, a duration reached)"""
        deadline = self.schedule.next_deadline()
        if self.schedule.skipped:
            logm.console.log(f"🗓️ {self.schedule.skipped} deadline(s) passed during the previous round, not made up for")
        if deadline > self.schedule.now():
            logm.console.log(f"🗓️ next round at {deadline.isoformat(sep=' ', timespec='seconds')}")
        # by short sleeps: SIGUSR1 and the clock-only criteria are looked at while waiting
        while (remaining := (deadline - self.schedule.now()).total_seconds()) > 0:
            time.sleep(min(remaining, 1.0))
            self._test_criteria(last_round, history, clock_only=True)
            if self.stop_reason is not None:
                return False
        return True

    def _test_criteria(self, server_round: int, history: History, clock_only: bool = False) -> None:
        for criterion in self.criteria:
            if clock_only and not criterion.CLOCK_ONLY:
                continue
            reason = criterion.should_stop(server_round, history)
            if reason:
                self.request_stop(reason)
                return

    def _run_round(self, current_round: int, timeout: Optional[float], history: History, start_time: float) -> bool:
        """False: a scheduled round no client trained in, neither evaluated nor counted; for a strategy
        that does not train, a scheduled round no client evaluated in, not counted"""
        log(INFO, "")
        log(INFO, "[ROUND %s]", current_round)
        res_fit = self.fit_round(server_round=current_round, timeout=timeout)
        counts_by_sites = self.schedule is not None or self.stop_without_new_data
        # otherwise a round all clients failed still counts: num_rounds bounds a session whose
        # clients keep failing
        if self.trains and counts_by_sites and (res_fit is None or not res_fit[2][0]):
            return False
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
        if not self.trains and counts_by_sites:
            # no fit to count the round by: its evaluations by the sites (none without new validation data)
            return res_fed is not None and bool(res_fed[2][0])
        return True
