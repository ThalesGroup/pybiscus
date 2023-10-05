import torch.nn as nn
from einops.layers.torch import Rearrange


def net(input_shape: int = 3, mid_shape: int = 6, n_classes: int = 10):
    model = nn.Sequential(
        nn.Conv2d(input_shape, mid_shape, 5),
        nn.ReLU(),
        nn.MaxPool2d(2, 2),
        nn.Conv2d(mid_shape, 16, 5),
        nn.ReLU(),
        nn.MaxPool2d(2, 2),
        Rearrange("b c h w -> b (c h w)"),
        nn.Linear(16 * 5 * 5, 120),
        nn.ReLU(),
        nn.Linear(120, 84),
        nn.ReLU(),
        nn.Linear(84, n_classes),
    )
    return model
