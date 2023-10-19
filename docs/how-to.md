# How-tos

Here are a few guides to update Pybiscus with new datasets, and models, and such.

## How to add models in Pybiscus

Available models are located in `ml/models/`. To add a new model, follow the few points below:
* make a new subdirectory, like `ml/models/my-model/`
* create two files `my_model.py` and `lit_my_model.py`:
    - the first one contains the usual PyTorch NN Module that defines your model.
    - the second one contains the LightningModule based on the classical nn.module.
* if needed, add another directory `ml/models/my-model/all-things-needed/` which would contain all things necessary for your model to work properly: specific losses and metrics, dedicated torch modules, and so on.
* update the file `ml/registry.py`:
    - import your LightningModule;
    - update `model_registry` by adding a new key linking to your LightingModule.

## How to add datasets in Pybiscus

Available datasets are located in `ml/data/`. To add a new model, follow the few points below:
* make a new subdirectory, like `ml/data/my-data/`
* create two files `my_data.py` and `lit_my_data.py`:
    - the first one contains the usual PyTorch Dataset that defines your dataset.
    - the second one contains the LightningDataModule based on the classical torch.dataset.
* if needed, add another directory `ml/data/my-data/all-things-needed/` which would contain all things necessary for your dataset to work properly, in particular preprocessing.
* update the file `ml/registry.py`:
    - import your LightningDataModule;
    - update `datamodule_registry` by adding a new key linking to your LightingDataModule.