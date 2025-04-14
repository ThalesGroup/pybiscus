import tensorflow as tf
import numpy as np 
import random

random_seed = 1 
np.random.seed(random_seed)
random.seed(random_seed)
tf.random.set_seed(random_seed)


import flwr as fl

import common



num_clients=2
num_rounds=10
fraction_fit=1.0

losses=[]
accuracies=[]

def get_evaluate_fn(model):
    """Return an evaluation function for server-side evaluation."""

    # Load test data here to avoid the overhead of doing it in `evaluate` itself
    _, test = tf.keras.datasets.mnist.load_data()
    test_data, test_labels = test

    # preprocessing
    test_data, test_labels = common.preprocess(test_data, test_labels)

    # The `evaluate` function will be called after every round
    def evaluate(self,weights: fl.common.NDArrays,config):
        model.set_weights(weights)  # Update model with the latest parameters
        loss, accuracy = model.evaluate(test_data, test_labels)
        losses.append(loss)
        accuracies.append(accuracy)
        return loss, {"accuracy": accuracy}

    return evaluate



model = common.create_cnn_model()
loss = tf.keras.losses.CategoricalCrossentropy(from_logits=True)
model.compile("sgd", loss=loss, metrics=["accuracy"])
strategy = fl.server.strategy.FedAvg(
    fraction_fit=fraction_fit,
    min_available_clients=num_clients,
    evaluate_fn=get_evaluate_fn(model),
    initial_parameters=fl.common.ndarrays_to_parameters(model.get_weights()),
)
fl.server.start_server(
    server_address="0.0.0.0:8080",
    strategy=strategy,
    config=fl.server.ServerConfig(num_rounds=num_rounds),
)



print("server losses:")
print(losses)
print("server accuracies")
print(accuracies)