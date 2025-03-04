import torch.nn as nn
from einops.layers.torch import Rearrange

def net(input_shape: int = 3, mid_shape: int = 6, n_classes: int = 10) -> nn.Module:
    """
    Defines a simple convolutional neural network (CNN) using PyTorch and the einops library 
    for tensor rearrangement. 
    This network is designed for image classification tasks, 
    such as those involving the CIFAR-10 dataset.

    Network Architecture

    1) Input Layer:

        The network expects input images with input_shape channels (e.g., 3 for RGB images).

    2) First Convolutional Block:

        nn.Conv2d(input_shape, mid_shape, 5): 
            A convolutional layer with mid_shape filters, each of size 5x5.
        nn.ReLU(): 
            Applies the ReLU activation function.
        nn.MaxPool2d(2, 2): 
            A max-pooling layer with a 2x2 window to downsample the spatial dimensions.

    3) Second Convolutional Block:

        nn.Conv2d(mid_shape, 16, 5): 
            Another convolutional layer with 16 filters, each of size 5x5.
        nn.ReLU(): 
            Applies the ReLU activation function.
        nn.MaxPool2d(2, 2): 
            Another max-pooling layer with a 2x2 window.

    4) Rearrangement Layer:

        Rearrange("b c h w -> b (c h w)"): 
            Flattens the tensor from shape (batch_size, channels, height, width) 
            to (batch_size, channels * height * width) 
            to prepare it for the fully connected layers.

    5) Fully Connected Layers:

        nn.Linear(16 * 5 * 5, 120): 
            A fully connected layer with 120 output features.
        nn.ReLU(): 
            Applies the ReLU activation function.
        nn.Linear(120, 84): 
            Another fully connected layer with 84 output features.
        nn.ReLU(): 
            Applies the ReLU activation function.
        nn.Linear(84, n_classes): 
            The final fully connected layer with n_classes output features, 
            representing the number of classes in the classification task.

    Key Points

        Rearrange Layer:
            The Rearrange function from the einops library is used to reshape the tensor. 
            It provides a concise and readable way to specify tensor rearrangements using string notation.

        Model Flexibility:
            The input_shape, mid_shape, and n_classes parameters allow for easy customization of the network architecture 
            for different input shapes and classification tasks.

        Typical Use Case:
            This architecture is suitable for image classification tasks with input images of size 32x32 pixels, 
            such as the CIFAR-10 dataset.
    """

    model = nn.Sequential(

        # First Convolutional Block:
        nn.Conv2d(input_shape, mid_shape, 5),
        nn.ReLU(),
        nn.MaxPool2d(2, 2),

        # Second Convolutional Block:
        nn.Conv2d(mid_shape, 16, 5),
        nn.ReLU(),
        nn.MaxPool2d(2, 2),

        # Rearrangement Layer:
        Rearrange("b c h w -> b (c h w)"),

        # Fully Connected Layers:
        nn.Linear(16 * 5 * 5, 120),
        nn.ReLU(),
        nn.Linear(120, 84),
        nn.ReLU(),
        nn.Linear(84, n_classes),
    )

    return model
