from typing import List, Tuple, Optional, Dict, Union, Callable, Any
from flwr.server.strategy import Strategy
from flwr.common import EvaluateIns, EvaluateRes, FitIns, FitRes, Parameters, Scalar
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
import logging

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator

# Configuration du logger (optionnel)
logger = logging.getLogger(__name__)

class StrategyDecoratorWithHooks(StrategyDecorator):
    """
    Generic decorator for Flower Strategy with a hook system
    """

    def __init__(self, base_strategy: Strategy):
        """
        Initialize the decorator with a base strategy.
        
        Parameters
        ----------
        base_strategy : Strategy
            The strategy to decorate
        """
        super().__init__(base_strategy)
        
        # hooks
        self._hooks = {
            'before_initialize_parameters': [],
            'after_initialize_parameters': [],
            'before_configure_fit': [],
            'after_configure_fit': [],
            'before_aggregate_fit': [],
            'after_aggregate_fit': [],
            'before_configure_evaluate': [],
            'after_configure_evaluate': [],
            'before_aggregate_evaluate': [],
            'after_aggregate_evaluate': [],
            'before_evaluate': [],
            'after_evaluate': [],
        }
        
        # counters and stats
        self._stats = {
            'rounds_completed': 0,
            'total_clients_trained': 0,
            'total_clients_evaluated': 0,
            'total_failures': 0
        }
        
        logger.info(f"StrategyDecorator wrapping: {type(base_strategy).__name__}")

    def add_hook(self, hook_name: str, hook_function: Callable) -> None:
        """
        Add a hook function to be executed at specific points.
        
        Parameters
        ----------
        hook_name : str
            Name of the hook point (e.g., 'before_aggregate_fit')
        hook_function : Callable
            Function to execute at the hook point
        """
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}. Available hooks: {list(self._hooks.keys())}")
        
        self._hooks[hook_name].append(hook_function)
        logger.debug(f"Added hook '{hook_name}': {hook_function.__name__}")

    def remove_hook(self, hook_name: str, hook_function: Callable) -> bool:
        """
        Remove a specific hook function.
        
        Returns
        -------
        bool
            True if hook was removed, False if not found
        """
        if hook_name in self._hooks and hook_function in self._hooks[hook_name]:
            self._hooks[hook_name].remove(hook_function)
            logger.debug(f"Removed hook '{hook_name}': {hook_function.__name__}")
            return True
        return False

    def _execute_hooks(self, hook_name: str, *args, **kwargs) -> None:
        """Execute all registered hooks for a given hook point."""
        for hook_func in self._hooks.get(hook_name, []):
            try:
                hook_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook '{hook_name}' failed: {e}")
                # resume execution even if a hook fails

    def get_stats(self) -> Dict[str, Any]:
        """Return decorator statistics."""
        return dict(self._stats)

    def initialize_parameters(self, client_manager: ClientManager) -> Optional[Parameters]:
        """Initialize parameters with before/after hooks."""
        self._execute_hooks('before_initialize_parameters', client_manager)
        
        result = self.base_strategy.initialize_parameters(client_manager)
        
        self._execute_hooks('after_initialize_parameters', client_manager, result)
        
        return result

    def configure_fit(
        self, 
        server_round: int, 
        parameters: Parameters, 
        client_manager: ClientManager
    ) -> List[Tuple[ClientProxy, FitIns]]:
        """Configure fit with before/after hooks."""
        self._execute_hooks('before_configure_fit', server_round, parameters, client_manager)
        
        result = self.base_strategy.configure_fit(server_round, parameters, client_manager)
        
        # statistics update
        self._stats['total_clients_trained'] += len(result)
        
        self._execute_hooks('after_configure_fit', server_round, parameters, client_manager, result)
        
        return result

    def aggregate_fit(
        self, 
        server_round: int, 
        results: List[Tuple[ClientProxy, FitRes]], 
        failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]]
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """Aggregate fit results with before/after hooks."""
        self._execute_hooks('before_aggregate_fit', server_round, results, failures)
        
        # statistics update
        self._stats['total_failures'] += len(failures)
        
        aggregated_parameters, aggregated_metrics = self.base_strategy.aggregate_fit(
            server_round, results, failures
        )
        
        # enrich metrics with decorator info
        if aggregated_metrics is not None:
            aggregated_metrics = dict(aggregated_metrics)
            aggregated_metrics.update({
                'decorator_stats_failures': len(failures),
                'decorator_stats_successful': len(results),
            })
        
        self._execute_hooks('after_aggregate_fit', server_round, results, failures, 
                          aggregated_parameters, aggregated_metrics)
        
        return aggregated_parameters, aggregated_metrics

    def configure_evaluate(
        self, 
        server_round: int, 
        parameters: Parameters, 
        client_manager: ClientManager
    ) -> List[Tuple[ClientProxy, EvaluateIns]]:
        """Configure evaluate with before/after hooks."""
        self._execute_hooks('before_configure_evaluate', server_round, parameters, client_manager)
        
        result = self.base_strategy.configure_evaluate(server_round, parameters, client_manager)
        
        # statistics update
        self._stats['total_clients_evaluated'] += len(result)
        
        self._execute_hooks('after_configure_evaluate', server_round, parameters, client_manager, result)
        
        return result
        
    def aggregate_evaluate(
        self, 
        server_round: int,
        results: List[Tuple[ClientProxy, EvaluateRes]], 
        failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]]
    ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        """Aggregate evaluate results with before/after hooks."""
        self._execute_hooks('before_aggregate_evaluate', server_round, results, failures)
        
        # statistics update
        self._stats['rounds_completed'] = server_round
        self._stats['total_failures'] += len(failures)
        
        aggregated_loss, aggregated_metrics = self.base_strategy.aggregate_evaluate(
            server_round, results, failures
        )
        
        # enrich metrics with decorator info
        if aggregated_metrics is not None:
            aggregated_metrics = dict(aggregated_metrics)
            aggregated_metrics.update({
                'decorator_stats_eval_failures': len(failures),
                'decorator_stats_eval_successful': len(results),
            })
        
        self._execute_hooks('after_aggregate_evaluate', server_round, results, failures,
                          aggregated_loss, aggregated_metrics)
        
        return aggregated_loss, aggregated_metrics

    def evaluate(
        self, 
        server_round: int, 
        parameters: Parameters
    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        """Centralized evaluation with before/after hooks."""
        self._execute_hooks('before_evaluate', server_round, parameters)
        
        result = self.base_strategy.evaluate(server_round, parameters)
        
        self._execute_hooks('after_evaluate', server_round, parameters, result)
        
        return result

    # Redirection des attributs vers la stratégie de base
    # redirect attributes to base strategy
    def __getattr__(self, name: str) -> Any:
        """
        Forward any unknown attributes to the base strategy.
        Cela permet d'accéder aux attributs de la stratégie originale.
        """
        return getattr(self.base_strategy, name)

    def __repr__(self) -> str:
        """String representation of the decorated strategy."""
        return f"StrategyDecorator({self.base_strategy})"
