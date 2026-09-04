from typing import override, Optional

import numpy as np
import lightning.pytorch as pl
import torchvision.transforms as transforms

from torch.utils.data import DataLoader, Subset
from torchvision.datasets import CIFAR10

import pybiscus.core.pybiscus_logger as logm
import argparse
import random


class CifarLightningDataModule(pl.LightningDataModule):
    """
    A LightningDataModule is an abstract class provided by PyTorch Lightning 
    that simplifies data management in machine learning workflows. 
    It helps structure code by separating data preparation logic from the model training logic, 
    making the code more modular and reusable. 

    Role:

        1) Data Encapsulation:

           * Centralizes data loading and preparation logic, 
           separating these concerns from the model training logic.

        2) Reusability:

            * Facilitates the reuse of data management code across different projects or experiments.
    
        3) Integration with PyTorch Lightning:

            * Seamlessly integrates with other PyTorch Lightning components, i
            such as the Trainer, to automate training and evaluation processes.

    API:

        1) __init__(self, *args, **kwargs)

            * Description: 
                Initializes the data module with necessary parameters, such as data paths, batch size, etc.

            * Parameters:
                *args, **kwargs: Application-specific parameters, such as 
                data paths, batch size, number of workers, etc.

        2) prepare_data(self)

            * Description: 
                Used to download data if necessary. 
                This method is called only once per node, which is useful for downloading data across multiple nodes.

        3) setup(self, stage: Optional[str] = None)

            * Description: 
                Prepares datasets for different stages (training, validation, testing).

            * Parameters:
                stage: Current stage ("fit" for training and validation, "test" for testing, or None for all stages).
    
        4) train_dataloader(self) -> DataLoader

            * Description: 
                Returns a DataLoader for the training dataset.
    
        5) val_dataloader(self) -> DataLoader

            * Description: 
                Returns a DataLoader for the validation dataset.
    
        6) test_dataloader(self) -> DataLoader

            * Description: 
                Returns a DataLoader for the test dataset.
    
        7) teardown(self, stage: Optional[str] = None)

            * Description: 
                Used to clean up resources after a stage has run, such as deleting temporary files.

            * Parameters:
                stage: Current stage ("fit", "test", or None).

     ----------------------------------

    torch.utils.data.DataLoader is a crucial component in PyTorch for efficiently loading and iterating over datasets. 
    It provides an iterable over a given dataset, enabling easy access to data samples, 
    batching, shuffling, and parallel data loading.

    Purpose of DataLoader

        1) Batching:

            Automatically groups data samples into batches, 
            which is essential for training machine learning models efficiently.

        2) Shuffling:

            Randomly shuffles the data at each epoch, which helps in training models 
            by preventing them from learning the order of the data.

        3) Parallel Data Loading:

            Utilizes multiple subprocesses to load data in parallel, 
            which can significantly speed up the data loading process, especially for large datasets.

        4) Customization:

            Allows customization of data loading behavior through various parameters and custom collate functions.

    Key Features and Parameters

        1) dataset (Dataset):

            The dataset from which to load the data. It should be an instance of a torch.utils.data.Dataset or a subclass.

        2) batch_size (int, optional):

            The number of samples per batch to load. 
            Default is 1.

        3) shuffle (bool, optional):

            If True, data is reshuffled at every epoch. 
            Default is False.

        4) num_workers (int, optional):

            The number of subprocesses to use for data loading. 0 means that the data will be loaded in the main process. 
            Default is 0.

        5) collate_fn (callable, optional):

            Merges a list of samples to form a mini-batch of Tensor(s). 
            Used when samples are of varying sizes or types.

        6) drop_last (bool, optional):

            If True, the last batch is dropped if it is smaller than batch_size. 
            Default is False.

     ----------------------------------

     The torch.utils.data.Dataset class in PyTorch is an abstract class representing a dataset. 
     It provides a way to access data samples and their corresponding labels, 
     making it a fundamental component for loading and iterating over data in PyTorch. 

    Purpose:

        * Data Abstraction:

            Provides a consistent interface for accessing data samples and their corresponding labels.

        * Customization:

            Allows for the creation of custom datasets by subclassing and implementing specific methods.

    Key Methods:

        1) __len__(self)

            Description: 
                Returns an integer representing the size of the dataset.

        2) __getitem__(self, index)

            Description: 
                Retrieves the sample and its corresponding label at the given index.
                The format can vary depending on the dataset (e.g., a tuple of tensor(s)).

    """

    @override
    def __init__( self, dir_train, data_train_indices_path, data_val_indices_path, dir_test, dir_privacy, batch_size, num_workers: int = 0,):

        super().__init__()

        # init parameters memo
        self.data_dir_train = dir_train
        self.data_train_indices_path = data_train_indices_path
        self.data_val_indices_path = data_val_indices_path
        self.data_dir_test  = dir_test
        self.data_dir_privacy = dir_privacy
        self.num_workers    = num_workers
        self.batch_size     = batch_size

        self.transform      = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            ]
        )

        # DataLoaders for train, val and test phasis
        self.data_train     = None
        self.data_val       = None
        self.data_test      = None

        # DataLoader specific for the privacy evaluation (must contains data from the
        # targeted participant training sets, and other data like validation and test)
        self.privacy_set_dataloader = None

    @override
    def setup(self, stage: Optional[str] = None):
        """
        data downloaded according to stage:

                   | Train | Val | Test |
            -----------------------------
            "fit"  |   X   |  X  |  _   |
            -----------------------------
            "test" |   _   |  _  |  X   |
            -----------------------------
            None   |   X   |  X  |  X   |
            -----------------------------
        """

        if stage == "fit" or stage is None:
            cifar10_trainval = CIFAR10( root=self.data_dir_train, train=True,  download=True, transform=self.transform,)
            if self.data_train_indices_path is None:
                self.data_train = cifar10_trainval
                logm.console.log("x_train shape: ", self.data_train.data.shape)

            else:
                data_train_indices = self._read_file_indices(self.data_train_indices_path)
                self.data_train = Subset(cifar10_trainval, data_train_indices)
                
            if self.data_val_indices_path is None:
                self.data_val   = cifar10_trainval
                logm.console.log("y_train shape: ", self.data_val.data.shape)
            else:
                data_val_indices = self._read_file_indices(self.data_val_indices_path)
                self.data_val = Subset(cifar10_trainval, data_val_indices)
                logm.console.log("x_train shape: ", len(self.data_val.indices))
            

            # print number of targets and  values targets
            # logm.console.log("Number of Targets :", len(np.unique(self.data_train.targets)))
            # logm.console.log("Targets Values    :",     np.unique(self.data_train.targets))

        if stage == "test" or stage is None:
            self.data_test  = CIFAR10( root=self.data_dir_test,  train=True, download=True, transform=self.transform,)
            logm.console.log("x_test shape", self.data_test.data.shape)
            if self.data_dir_privacy is not None:
                self.privacy_set  = CIFAR10( root=self.data_dir_privacy,  train=True, download=True, transform=self.transform,)
                self.privacy_set_dataloader = DataLoader( self.data_test,  batch_size=self.batch_size, num_workers=self.num_workers, drop_last=True, shuffle=False,)
                logm.console.log("x_privacy shape", self.privacy_set.data.shape)

    def _read_file_indices(self,filepath):
        """
            Return a list containing all integers seperated with whitespaces present in the file
        """
        list_indices = []
        with open(filepath, 'r') as file:
            for line in file:
                for d in line.strip().split():
                    if d.isdigit():
                        list_indices.append(int(d))
        return list_indices

    @override
    def train_dataloader(self) -> DataLoader:

        if self.data_train is None:
            raise ValueError("Train dataset undefined: bad setup")
        
        return DataLoader( self.data_train, batch_size=self.batch_size, num_workers=self.num_workers, drop_last=True, shuffle=True,)

    @override
    def val_dataloader(self) -> DataLoader:

        if self.data_val is None:
            raise ValueError("Val dataset undefined: bad setup")
        
        return DataLoader( self.data_val,   batch_size=self.batch_size, num_workers=self.num_workers, drop_last=True, shuffle=False,)

    @override
    def test_dataloader(self) -> DataLoader:

        if self.data_test is None:
            raise ValueError("Test dataset undefined: bad setup")
        
        return DataLoader( self.data_test,  batch_size=self.batch_size, num_workers=self.num_workers, drop_last=True, shuffle=False,)


def write_list_to_file(list_indices, output_path):
    L = [f"{d}\n" for d in list_indices]
    with open(output_path, "w") as fp:
        fp.writelines(L)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Create Non overlapping datasets for Federated Learning")
    parser.add_argument("--nb_clients", type=int, required=True, help="Nombre de clients")
    parser.add_argument("--data_path", type=str, required=True, help="Path to the root dataset that is splitted")
    parser.add_argument("--output_folder", type=str, required=True, help="Path to where the indices list will be stored")
    
    args = parser.parse_args()
    
    cifar10_trainval = CIFAR10( root=args.data_path, train=True,  download=True)
    shuffled_indices = [i for i in range(len(cifar10_trainval))]
    random.shuffle(shuffled_indices)

    nb_indices_client = int(len(shuffled_indices)/args.nb_clients)

    for client in range(args.nb_clients):
        client_indices = shuffled_indices[client*nb_indices_client: (client+1)*nb_indices_client]
        write_list_to_file(
            client_indices[:int(len(client_indices)*0.8)], 
            f"{args.output_folder}/client_{client}_train.txt"
            )
        write_list_to_file(
            client_indices[int(len(client_indices)*0.8):], 
            f"{args.output_folder}/client_{client}_val.txt"
            )
