import tensorflow as tf
import random
import numpy as np 
random_seed = 2 
np.random.seed(random_seed)
random.seed(random_seed)
tf.random.set_seed(random_seed)


from tensorflow_privacy.privacy.optimizers.dp_optimizer_keras_vectorized import (
    VectorizedDPKerasSGDOptimizer,
)

import flwr as fl
import common



# Make TensorFlow logs less verbose
# os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# global for tracking privacy
PRIVACY_LOSS = 0
num_clients=2
partition=1
local_epochs=1
batch_size=32
learning_rate=0.15
l2_norm_clip=1.0
noise_multiplier=0.3
microbatches=32
dpsgd=True

# Define Flower client
class MnistClient(fl.client.NumPyClient):
    def __init__(self, model, x_train, y_train, x_test, y_test,batch_size,local_epochs,dpsgd):
        self.model = model
        self.x_train, self.y_train = x_train, y_train
        self.x_test, self.y_test = x_test, y_test
        self.batch_size = batch_size
        self.local_epochs = local_epochs
        self.dpsgd = dpsgd

        if dpsgd:
            self.noise_multiplier = noise_multiplier
            if batch_size % microbatches != 0:
                raise ValueError(
                    "Number of microbatches should divide evenly batch_size"
                )
            optimizer = VectorizedDPKerasSGDOptimizer(
                l2_norm_clip=l2_norm_clip,
                noise_multiplier=noise_multiplier,
                num_microbatches=microbatches,
                learning_rate=learning_rate,
            )
            # Compute vector of per-example loss rather than its mean over a minibatch.
            loss = tf.keras.losses.CategoricalCrossentropy(
                from_logits=True, reduction=tf.losses.Reduction.NONE
            )
        else:
            optimizer = tf.keras.optimizers.SGD(learning_rate=learning_rate)
            loss = tf.keras.losses.CategoricalCrossentropy(from_logits=True)

        # Compile model with Keras
        model.compile(optimizer=optimizer, loss=loss, metrics=["accuracy"])

    def get_parameters(self, config):
        """Get parameters of the local model."""
        raise Exception("Not implemented (server-side parameter initialization)")

    def fit(self, parameters, config):
        """Train parameters on the locally held training set."""
        # Update local model parameters
        global PRIVACY_LOSS
        if self.dpsgd:
            privacy_spent = common.compute_epsilon(
                self.local_epochs,
                len(self.x_train),
                self.batch_size,
                self.noise_multiplier,
            )
            PRIVACY_LOSS += privacy_spent

        self.model.set_weights(parameters)
        # Train the model
        self.model.fit(
            self.x_train,
            self.y_train,
            epochs=self.local_epochs,
            batch_size=self.batch_size,
        )

        return self.model.get_weights(), len(self.x_train), {}

    def evaluate(self, parameters, config):
        """Evaluate parameters on the locally held test set."""

        # Update local model with global parameters
        self.model.set_weights(parameters)

        # Evaluate global model parameters on the local test data and return results
        loss, accuracy = self.model.evaluate(self.x_test, self.y_test)
        num_examples_test = len(self.x_test)
        return loss, num_examples_test, {"accuracy": accuracy}


# Load Keras model
model = common.create_cnn_model()

# Load a subset of MNIST to simulate the local data partition
(x_train, y_train), (x_test, y_test) = common.load(num_clients)[partition]
print("number of training points)",len(x_train))
print("Delta is set to approximate 1 / (number of training points): ",1/len(x_train))
# drop samples to form exact batches for dpsgd
# this is necessary since dpsgd is sensitive to uneven batches
# due to microbatching
if dpsgd and x_train.shape[0] % batch_size != 0:
    drop_num = x_train.shape[0] % batch_size
    x_train = x_train[:-drop_num]
    y_train = y_train[:-drop_num]

# Start Flower client
client = MnistClient(model, x_train, y_train, x_test, y_test,batch_size,local_epochs,dpsgd)
fl.client.start_numpy_client(server_address="127.0.0.1:8080", client=client)
if dpsgd:
    print("Privacy Loss: ", PRIVACY_LOSS)

