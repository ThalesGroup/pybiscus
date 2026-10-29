from typing import ClassVar, List, Tuple, Optional, Dict, Union
from flwr.server.strategy import Strategy
from flwr.common import EvaluateIns, EvaluateRes, FitIns, FitRes, Parameters, Scalar
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

def strategy_trains(strategy: Strategy) -> bool:
    """False when a decorator of the pipeline declares that no client trains (TRAINS): the server then
    counts a round by its evaluations, a scheduled round having no fit to count it by"""
    while strategy is not None:
        if getattr(type(strategy), "TRAINS", True) is False:
            return False
        strategy = getattr(strategy, "base_strategy", None)
    return True


class StrategyDecorator(Strategy):

    TRAINS: ClassVar[bool] = True

    def __init__(self, base_strategy: Strategy):
        super().__init__()

        self.base_strategy = base_strategy

    def initialize_parameters( self, client_manager: ClientManager 
                    ) -> Optional[Parameters]:
        return self.base_strategy.initialize_parameters( client_manager )

    def configure_fit( self, server_round: int, parameters: Parameters, client_manager: ClientManager
                    ) -> List[Tuple[ClientProxy, FitIns]]:
        return self.base_strategy.configure_fit( server_round, parameters, client_manager, )

    def aggregate_fit( self, server_round: int, 
                        results: List[Tuple[ClientProxy, FitRes]], failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]],
                    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        return self.base_strategy.aggregate_fit( server_round, results, failures, )

    def configure_evaluate( self, server_round: int, parameters: Parameters, client_manager: ClientManager
                    ) -> List[Tuple[ClientProxy, EvaluateIns]]:
        return self.base_strategy.configure_evaluate( server_round, parameters, client_manager )
        
    def aggregate_evaluate( self, server_round: int,
                        results: List[Tuple[ClientProxy, EvaluateRes]], failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]],
                    ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        return self.base_strategy.aggregate_evaluate( server_round, results, failures, )

    def evaluate( self, server_round: int, parameters: Parameters
                    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        return self.base_strategy.evaluate( server_round, parameters, )
