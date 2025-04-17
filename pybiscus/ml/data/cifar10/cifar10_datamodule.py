from typing import override, Optional

import numpy as np
import lightning.pytorch as pl
import torchvision.transforms as transforms

from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10

from pybiscus.core.console import console

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
    def __init__( self, dir_train, dir_val, dir_test, batch_size, num_workers: int = 0,):

        super().__init__()

        # init parameters memo
        self.data_dir_train = dir_train
        self.data_dir_val   = dir_val
        self.data_dir_test  = dir_test
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
            self.data_train = CIFAR10( root=self.data_dir_train, train=True,  download=True, transform=self.transform,)
            console.log("x_train shape: ", self.data_train.data.shape)
            self.data_val   = CIFAR10( root=self.data_dir_val,   train=False, download=True, transform=self.transform,)
            console.log("y_train shape: ", self.data_val.data.shape)

            # print number of targets and  values targets
            console.log("Number of Targets :", len(np.unique(self.data_train.targets)))
            console.log("Targets Values    :",     np.unique(self.data_train.targets))

        if stage == "test" or stage is None:
            self.data_test  = CIFAR10( root=self.data_dir_test,  train=False, download=True, transform=self.transform,)
            console.log("x_test shape", self.data_test.data.shape)

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

