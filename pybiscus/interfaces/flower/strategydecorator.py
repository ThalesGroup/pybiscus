from typing import List, Tuple, Optional, Dict, Union
from flwr.server.strategy import Strategy
from flwr.common import EvaluateIns, EvaluateRes, FitIns, FitRes, Parameters, Scalar
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

class StrategyDecorator(Strategy):

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
