import torch.nn as nn
import torch

# Example taken from https://www.kaggle.com/code/jinsolkwon/rul-predictions-using-pytorch-lstm#1.-Data-Processing


class LSTMRegressor(nn.Module):

    def __init__(self, n_features, hidden_units):
        super().__init__()
        self.n_features = n_features
        self.hidden_units = hidden_units
        self.n_layers = 1
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=self.hidden_units,
            batch_first=True,
            num_layers=self.n_layers,
        )
        self.linear1 = nn.Linear(in_features=self.hidden_units, out_features=12)
        self.relu1 = nn.ReLU()
        self.linear2 = nn.Linear(in_features=12, out_features=12)
        self.relu2 = nn.ReLU()
        self.linear3 = nn.Linear(in_features=12, out_features=1)

    def forward(self, x):
        batch_size = x.shape[0]
        h0 = (
            torch.zeros(self.n_layers, batch_size, self.hidden_units)
            .requires_grad_()
            .to(x.get_device())
        )
        c0 = (
            torch.zeros(self.n_layers, batch_size, self.hidden_units)
            .requires_grad_()
            .to(x.get_device())
        )
        _, (hn, _) = self.lstm(x, (h0, c0))
        out = self.linear1(hn[0])
        out = self.relu1(out)
        out = self.linear2(out)
        out = self.relu2(out)
        out = self.linear3(out).flatten()

        return out
