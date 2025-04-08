# How-tos

Here are a few guides to update Pybiscus with new datasets, and models, and such.

## How to add models in Pybiscus

Available models are located in `ml/models/`. To add a new model, follow the few points below:

1. make a new subdirectory, like `ml/models/my-model/`
2. create two files `my_model.py` and `lit_my_model.py`:
    - the first one contains the usual PyTorch NN Module that defines your model.
    - the second one should contain:
        - the LightningModule based on the classical nn.module;
        - a Pydantic BaseModel that reproduces the __init__ parameters needed for the LightningModule
        - a Pydantic BaseModel similar to `src.ml.models.cnn.lit_cnn.ConfigModel_Cifar10`.
        - a Signature for both training and evaluation steps, as in `src.ml.models.cnn.lit_cnn.CNNSignature`. This is necessary in order for the train and test loops to work.
3. if needed, add another directory `ml/models/my-model/all-things-needed/` which would contain all things necessary for your model to work properly: specific losses and metrics, dedicated torch modules, and so on.
4. update the file `ml/registry.py`:
    - import your LightningModule;
    - update `model_registry` by adding a new key linking to your LightingModule.
5. of course, add the needed Python libraries using uv
```bash
uv add needed-library1 needed-library2 ...
```

## How to add datasets in Pybiscus

Available datasets are located in `ml/data/`. To add a new model, follow the few points below:

1. make a new subdirectory, like `ml/data/my-data/`
2. create two files `my_data.py` and `lit_my_data.py`:
    - the first one contains the usual PyTorch Dataset that defines your dataset.
    - the second one contains the LightningDataModule based on the classical torch.dataset.
3. if needed, add another directory `ml/data/my-data/all-things-needed/` which would contain all things necessary for your dataset to work properly, in particular preprocessing.
4. update the file `ml/registry.py`:
    - import your LightningDataModule;
    - update `datamodule_registry` by adding a new key linking to your LightingDataModule.
