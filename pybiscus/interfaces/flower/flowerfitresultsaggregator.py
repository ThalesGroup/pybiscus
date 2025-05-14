
from typing import Union
from flwr.server.client_proxy import ClientProxy

from flwr.common import FitRes, Parameters

class FlowerFitResultsAggregator:

    def aggregate( 
            self,
            server_round: int, 
            results: list[tuple[ClientProxy, FitRes]], 
            failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
            ) -> Parameters:
        raise NotImplementedError("Implement the aggregator.")
