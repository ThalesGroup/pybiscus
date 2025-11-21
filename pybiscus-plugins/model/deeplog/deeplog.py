import torch
import torch.nn as nn
from torch.autograd import Variable

class DeepLog(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_keys):
        super(DeepLog, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size,
                            hidden_size,
                            num_layers,
                            batch_first=True)
        self.fc = nn.Linear(hidden_size, num_keys)

    def forward(self, features):

        # import pybiscus.core.pybiscuscontext as pcpc
        # device = pcpc.pybiscus_context["model"].device

        input0 = features
        h0 = torch.zeros(self.num_layers, input0.size(0),
                         self.hidden_size,
                         device=features.device)
        c0 = torch.zeros(self.num_layers, input0.size(0),
                         self.hidden_size,
                         device=features.device)
        out, _ = self.lstm(input0, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out


# def deeplog(input_size: int = 1, hidden_size: int = 64, num_layers: int = 2, num_keys: int = 33) -> nn.Module:
#     """
#     Defines a DeepLog-style model using LSTM layers for sequence modeling in log anomaly detection tasks.

#     Network Architecture

#     1) Input Layer:
#         Expects input sequences of shape (batch_size, sequence_length, input_size).

#     2) LSTM Layer(s):
#         nn.LSTM(input_size, hidden_size, num_layers, batch_first=True):
#             A multi-layer LSTM that processes input sequences and learns temporal patterns.

#     3) Final Hidden State Extraction:
#         out[:, -1, :] selects the output at the last time step from the final LSTM layer,
#         representing the summary of the sequence.

#     4) Fully Connected Layer:
#         nn.Linear(hidden_size, num_keys):
#             Maps the final LSTM output to the number of possible next log keys for prediction.

#     Parameters:
#         input_size (int): Dimensionality of input features at each time step.
#         hidden_size (int): Number of hidden units in each LSTM layer.
#         num_layers (int): Number of stacked LSTM layers.
#         num_keys (int): Number of unique log keys (classes) to predict.

#     Typical Use Case:
#         This architecture is suitable for log anomaly detection using sequences of event embeddings.
#     """
    
#     class DeepLogModel(nn.Module):
#         def __init__(self, input_size, hidden_size, num_layers, num_keys):
#             super().__init__()
#             self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
#             self.fc = nn.Linear(hidden_size, num_keys)

#         def forward(self, x):
#             # Initialize hidden and cell states with zeros (automatically handles device of x)
#             h0 = torch.zeros(self.lstm.num_layers, x.size(0), self.lstm.hidden_size, device=x.device)
#             c0 = torch.zeros(self.lstm.num_layers, x.size(0), self.lstm.hidden_size, device=x.device)
#             out, _ = self.lstm(x, (h0, c0))  # out: (batch_size, seq_len, hidden_size)
#             out = self.fc(out[:, -1, :])     # Use last time step
#             return out

#     return DeepLogModel(input_size, hidden_size, num_layers, num_keys)
