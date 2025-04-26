# How-to

Here are a few guides to update Pybiscus with new datasets, and models, and such.

## Pybiscus plugins

At launch, pybiscus looks for the file defined in PYBISCUS_PLUGIN_CONF_PATH
or by default at pybiscus-plugins-conf.yml .
It contains the definition of plugins that will be loaded :

data:
  - path: "./pybiscus-plugins/data"
    modules:
      - cifar10
      - randomvector
      - turbofan
model:
  - path: "./pybiscus-plugins/model"
    modules:
      - cnn
      - linearregression
      - lstm
strategy:
  - path: "./pybiscus-plugins/strategy"
    modules:
      - fedavg

The python path will be dynamically extended at run-time to include this directories.

## How to add models in Pybiscus

Available models are those located in either the plugin directory,
by instance: `./pybiscus-plugins/model/`
(requires also plugin configuration file update)
or in `.../ml/models/` pybiscus source tree. 


To add a new model, follow the few points below:

0. choose either plugin or pybiscus directory as ROOT
1. make a new subdirectory, like `$ROOT/my-model/`
2. create two files `my_model.py` and `lit_my_model.py`:
    - the first one contains the usual PyTorch NN Module that defines your model.
    - the second one should contain:
        - the LightningModule based on the classical nn.module;
        - a Pydantic BaseModel that reproduces the __init__ parameters needed for the LightningModule
        - a Pydantic BaseModel similar to `cnn.lit_cnn.ConfigModel_Cifar10`.
        - a Signature for both training and evaluation steps, as in `cnn.lit_cnn.CNNSignature`. This is necessary in order for the train and test loops to work.
3. if needed, add another directory `$ROOT/my-model/all-things-needed/` which would contain all things necessary for your model to work properly: specific losses and metrics, dedicated torch modules, and so on.
4. create the file `$ROOT/my-model/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from LightningModule
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from cnn.lit_cnn import ( LitCNN, ConfigModel_Cifar10, )

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

Available datasets are those located in either the plugin directory,
by instance: `./pybiscus-plugins/data/`
(requires also plugin configuration file update)
or in `.../ml/data/` pybiscus source tree. 

To add a new dataset, follow the few points below:

0. choose either plugin or pybiscus directory as ROOT
1. make a new subdirectory, like `$ROOT/my-data/`
2. create two files `my_data.py` and `lit_my_data.py`:
    - the first one contains the usual PyTorch Dataset that defines your dataset.
    - the second one contains the LightningDataModule based on the classical torch.dataset.
3. if needed, add another directory `$ROOT/my-data/all-things-needed/` which would contain all things necessary for your dataset to work properly, in particular preprocessing.
4. create the file `$ROOT/my-data/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from LightningDataModule
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python
from typing import Dict, List, Tuple
import lightning.pytorch as pl
from pydantic import BaseModel

from cifar10.cifar10_dataconfig import ConfigData_Cifar10 
from cifar10.cifar10_datamodule import CifarLightningDataModule 

def get_modules_and_configs() -> Tuple[Dict[str, pl.LightningDataModule], List[BaseModel]]:

    registry = {"cifar": CifarLightningDataModule,}
    configs  = [ConfigData_Cifar10]

    return registry, configs
```
5. of course, add the needed Python libraries using uv
```bash
uv add needed-library1 needed-library2 ...
```

## How to add strategies in Pybiscus

Available strategies are those located in either the plugin directory,
by instance: `./pybiscus-plugins/strategy/`
(requires also plugin configuration file update)
or in `.../flower/strategy/` pybiscus source tree. 

To add a new strategy, follow the few points below:

0. choose either plugin or pybiscus directory as ROOT
1. make a new subdirectory, like `$ROOT/my-strategy/`
2. create a file `my_strategy.py` implementing the flwr.server.strategy.Strategy class
3. create the file `$ROOT/my-strategy/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from flwr.server.strategy.Strategy
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python

from typing import Dict, List, Tuple
from pydantic import BaseModel
from flwr.server.strategy import Strategy

from fedavg.fedavgstrategy2 import FabricFedAvgStrategy2, ConfigFabricFedAvgStrategy2

def get_modules_and_configs() -> Tuple[Dict[str, Strategy], List[BaseModel]]:

    registry = { "fedavg2": FabricFedAvgStrategy2, }
    configs  = [ConfigFabricFedAvgStrategy2,]

    return registry, configs
```
5. of course, add the needed Python libraries using uv
```bash
uv add needed-library1 needed-library2 ...
```

At program launch, you will see the plugin manager and registry logs, 
loading plugins and registering models, datasets and strategies, for instance :

```bash
🔍 [plugins] Using config file: pybiscus-plugins-conf.yml
🔍 [plugins] Processing Pybiscus plugins 🧩
 🔍 [plugins] Processing category 'data'...
  ✅ Added 📦 './pybiscus-plugins/data' to sys.path
  ✅ 🧩 Successfully imported plugin 'cifar10'
  ✅ 🧩 Successfully imported plugin 'randomvector'
  ✅ 🧩 Successfully imported plugin 'turbofan'
 🔍 [plugins] Processing category 'model'...
  ✅ Added 📦 './pybiscus-plugins/model' to sys.path
  ✅ 🧩 Successfully imported plugin 'cnn'
  ✅ 🧩 Successfully imported plugin 'linearregression'
  ✅ 🧩 Successfully imported plugin 'lstm'
 🔍 [plugins] Processing category 'strategy'...
  ✅ Added 📦 './pybiscus-plugins/strategy' to sys.path
  ✅ 🧩 Successfully imported plugin 'fedavg'
🔍 [registry] Scanning submodules in: pybiscus.ml.data (./pybiscus/pybiscus/ml/data)
✅ [registry] Found submodules: []
📦 Loading module: cifar10
  ✅ Registered: cifar (CifarLightningDataModule)
📦 Loading module: randomvector
  ✅ Registered: randomvector (RandomVectorLightningDataModule)
📦 Loading module: turbofan
  ✅ Registered: turbofan (LitTurbofanDataModule)

📦 Total LightningDataModule(s) registered: 3
🧩 Total configs in union: 3

🔍 [registry] Scanning submodules in: pybiscus.ml.models (./pybiscus/pybiscus/ml/models)
✅ [registry] Found submodules: []
📦 Loading module: cnn
  ✅ Registered: cifar (LitCNN)
📦 Loading module: linearregression
  ✅ Registered: linearregression (LitLinearRegression)
📦 Loading module: lstm
  ✅ Registered: lstm (LitLSTMRegressor)

📦 Total LightningModule(s) registered: 3
🧩 Total configs in union: 3

🔍 [registry] Scanning submodules in: pybiscus.flower.strategy (./pybiscus/pybiscus/flower/strategy)
✅ [registry] Found submodules: ['pybiscus.flower.strategy.fedavg']
📦 Loading module: pybiscus.flower.strategy.fedavg
  ✅ Registered: fedavg (FabricFedAvgStrategy)
📦 Loading module: fedavg
  ✅ Registered: fedavg2 (FabricFedAvgStrategy2)

📦 Total Strategy(s) registered: 2
🧩 Total configs in union: 2

```
