"""Summary of the ml module for Hibiscus

This module holds both data and models for Federated Learning.
The data directory holds Torch Datasets and their corresponding Lightning DataModule.
Hibiscus works only with LightningDataModule.

The models directory holds Torch NN Module and their corresponding Lightning Modules.
Hibiscus works only with LightningModules.

The file registry.py contains three dictionnaries that holds Datasets, LightningModules
and LightninDataModules. Those three dictionnaries are used directly by the flower module,
which is the core of Hibiscus.

Hibiscus and its uses are firmly grounded by the Lightning API of its DataModule and
Module.

To add models or data, it suffices to add a subdirectory, aptly named, which would
contain Datasets/LightningDataModules, or Module/LightningModule. See both
data/cifar10 and models/cifar10 for examples.
"""
