
from collections import OrderedDict
import flwr as fl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from sklearn.model_selection import train_test_split
from torchvision.datasets import MNIST
from torchvision.transforms import Compose, Normalize, ToTensor
from tqdm import tqdm
import utils 
from phe import paillier
import numpy as np
import pickle
import numpy as np

torch.manual_seed(0)
np.random.seed(0)

#Load public-secret key
with open('keys.pkl', 'rb') as f:
    keys = pickle.load(f)
pk, sk = keys

print("Public Key",pk)

def KeyGen():
    public_key, private_key = paillier.generate_paillier_keypair(n_length=128)
    pk, sk = public_key, private_key
    return pk, sk


def encrypt(val, pk, precision):
    if isinstance(val, np.ndarray):
        if val.ndim == 1:
            return np.array([pk.encrypt(int(value * precision)) for value in val])
        else:
            return np.array([encrypt(sub_val, pk, precision) for sub_val in val])
    elif isinstance(val, list):
        return [encrypt(sub_val, pk, precision) for sub_val in val]
    else:
        return pk.encrypt(int(val * precision))

def decrypt(val, sk, precision):
    if isinstance(val, np.ndarray):
        if val.ndim == 1:
            return np.array([sk.decrypt(value) / precision for value in val])
        else:
            return np.array([decrypt(sub_val, sk, precision) for sub_val in val])
    elif isinstance(val, list):
        return [decrypt(sub_val, sk, precision) for sub_val in val]
    else:
        return sk.decrypt(val) / precision



precision = 2**32

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

net = utils.Net().to(DEVICE)
losses = []
accuracies = []


#NonIID Data 
trf = Compose([ToTensor(), Normalize((0.1307,), (0.3081,))])
train_dataset = MNIST("./data", train=True, download=True, transform=trf)
dist_client1 = [0, 10, 7, 90, 7000, 6100, 4000, 5100, 113, 6500]
client1_indices = []
for class_label in range(10):

    class_indices = [i for i, (_, label) in enumerate(train_dataset) if label == class_label]

    client1_count = dist_client1[class_label]
    client1_indices.extend(class_indices[:client1_count])

client1_dataset = Subset(train_dataset, client1_indices)



trainset,validset=train_test_split(client1_dataset, train_size=0.8,test_size=0.2, random_state=42)

trainloader = DataLoader(trainset, batch_size=32,shuffle=True)
validloader = DataLoader(validset, batch_size=32,shuffle=True)


# Define Flower client
class FlowerClient(fl.client.NumPyClient):
    def get_parameters(self, config):
        params=[val.cpu().numpy() for _, val in net.state_dict().items()] #retourner les les paramètres du modèle local
        enc=encrypt(params,pk,precision)
        return enc

    def set_parameters(self, parameters):
        parameters=decrypt(parameters, sk, precision)
        params_dict = zip(net.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        net.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        self.set_parameters(parameters) 
        utils.train(net, trainloader,DEVICE, epochs=1)
        s=self.get_parameters(config={})

        return s, len(trainloader.dataset), {}
    #Local test
    def evaluate(self, parameters, config):

        self.set_parameters(parameters)
        loss, accuracy = utils.test(net, validloader,DEVICE)
        losses.append(loss)
        accuracies.append(accuracy)
        print("Validation loss",loss,"  Validation accuracy:",accuracy)
        return loss, len(validloader.dataset), {"accuracy": accuracy}

# Start Flower client
fl.client.start_numpy_client(
    server_address="localhost:8081",
    client=FlowerClient(),
    grpc_max_message_length=1024*1024*1024
)
print("client2 losses:")
print(losses)
print("client2 accuracies")
print(accuracies)
loss_plot,accuracy_plot=utils.plot_loss_accuracy(losses, accuracies)
loss_plot.write_image("client2_validation_losses.png")
accuracy_plot.write_image("client2_validation_accuracies.png")
