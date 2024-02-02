from typing import List, Tuple
from tqdm import tqdm
import flwr as fl
from flwr.common import Metrics
from collections import OrderedDict
import torch
import numpy as np 
from flwr.common.typing import Scalar
import torch.nn as nn 
from typing import Dict, Callable, Optional, Tuple, List
from torchvision.datasets import MNIST
from torchvision.transforms import Compose, Normalize, ToTensor
from torch.utils.data import DataLoader
import utils 
import FedAvgHE
import numpy as np

torch.manual_seed(0)
np.random.seed(0)
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

losses = []
accuracies = []

_, _, test_set = utils.load_data()
def set_params(model: torch.nn.ModuleList, params: List[np.ndarray]):

    params_dict = zip(model.state_dict().keys(), params)
    state_dict = OrderedDict({k: torch.from_numpy(np.copy(v)) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)

def get_evaluate_fn(testset: MNIST,) -> Callable[[fl.common.NDArrays], Optional[Tuple[float, float]]]:
    def evaluate(
        server_round: int, parameters: fl.common.NDArrays, config: Dict[str, Scalar]
    ) -> Optional[Tuple[float, float]]:

        # determine device
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        model = utils.Net()
        set_params(model, parameters)
        model.to(device)

        #testloader = torch.utils.data.DataLoader(testset, batch_size=50)
        loss, accuracy = utils.test(model, testset, device=device)
        
        losses.append(loss)
        accuracies.append(accuracy)

        # return statistics
        return loss, {"Test accuracy": accuracy}
    
    return evaluate

def weighted_average(metrics: List[Tuple[int, Metrics]]) -> Metrics:
    # Multiply accuracy of each client by number of examples used
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    # Aggregate and return custom metric (weighted average)
    return {"accuracy": sum(accuracies) / sum(examples)}





strategy = FedAvgHE.FedAvgHE(min_available_clients=2,evaluate_metrics_aggregation_fn=weighted_average)#, evaluate_fn=get_evaluate_fn(test_set)#fl.server.strategy.FedAvg(min_available_clients=2,evaluate_metrics_aggregation_fn=weighted_average, evaluate_fn=get_evaluate_fn(test_set))

# Start Flower server
fl.server.start_server(
    server_address="localhost:8081",
    config=fl.server.ServerConfig(num_rounds=20),
    grpc_max_message_length=1024*1024*1024,
    strategy=strategy
)

loss_plot,accuracy_plot=utils.plot_loss_accuracy(losses, accuracies)
loss_plot.write_image("server_test_losses.png")
accuracy_plot.write_image("server_test_accuracies.png")
