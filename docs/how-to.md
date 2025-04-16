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
        - a Pydantic BaseModel similar to `pybiscus.ml.models.cnn.lit_cnn.ConfigModel_Cifar10`.
        - a Signature for both training and evaluation steps, as in `pybiscus.ml.models.cnn.lit_cnn.CNNSignature`. This is necessary in order for the train and test loops to work.
3. if needed, add another directory `ml/models/my-model/all-things-needed/` which would contain all things necessary for your model to work properly: specific losses and metrics, dedicated torch modules, and so on.
4. create the file `ml/models/my-data/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from LightningModule
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from pybiscus.ml.models.cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningModule], List[BaseModel]]:

    registry = { "cifar": LitCNN, }
    configs  = [ConfigModel_Cifar10]

    return registry, configs
```

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
4. create the file `ml/data/my-data/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from LightningDataModule
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from pybiscus.ml.data.cifar10.cifar10_dataconfig import ConfigData_Cifar10 
from pybiscus.ml.data.cifar10.cifar10_datamodule import CifarLightningDataModule 

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"cifar": CifarLightningDataModule,}
    configs  = [ConfigData_Cifar10]

    return registry, configs
```
5. of course, add the needed Python libraries using uv
```bash
uv add needed-library1 needed-library2 ...
```

At program launch, you will see the registry logs, loading modules and configuration, for instance :

🔍 [registry] Scanning submodules in: pybiscus.ml.data (./pybiscus/pybiscus/ml/data)
📦 Loading module: pybiscus.ml.data.cifar10
  ✅ Registered: cifar (CifarLightningDataModule)
📦 Loading module: pybiscus.ml.data.randomvector
  ✅ Registered: randomvector (RandomVectorLightningDataModule)
📦 Loading module: pybiscus.ml.data.turbofan
  ✅ Registered: turbofan (LitTurbofanDataModule)

📦 Total LightningDataModules registered: 3
🧩 Total configs in union: 3

🔍 [registry] Scanning submodules in: pybiscus.ml.models (./pybiscus/pybiscus/ml/models)
📦 Loading module: pybiscus.ml.models.cnn
  ✅ Registered: cifar (LitCNN)
📦 Loading module: pybiscus.ml.models.linearregression
  ✅ Registered: linearregression (LitLinearRegression)
📦 Loading module: pybiscus.ml.models.lstm
  ✅ Registered: lstm (LitLSTMRegressor)

📦 Total LightningModules registered: 3
🧩 Total configs in union: 3