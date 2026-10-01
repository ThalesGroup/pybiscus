# How-to

Here are a few guides to update Pybiscus with new datasets, and models, and such.

# How to add models in Pybiscus

For a comprehensive step-by-step guide to creating both models and data providers for PyBiscus, see [PyBiscus Integration Guide](pybiscus_model_guide.md).

This chapter covers the specific implementation details for model registration...

## Pybiscus plugins

At launch, Pybiscus reads the plugin manifest named by the environment variable
`PYBISCUS_PLUGIN_CONF_PATH` (which may be set in a `pybiscus.env` file), by default
`pybiscus-plugins-conf.yml`. Several manifests can be merged, separated by `:`
(`pybiscus-plugins-conf.yml:../my-project/my-plugins-conf.yml`); the paths in a manifest are
relative to it. An excerpt of the bundled one:

```yaml
data:
  - path: "./pybiscus-plugins/data"
    modules:
      - cifar10
      - mnist
      - turbofan
model:
  - path: "./pybiscus-plugins/model"
    modules:
      - cnn
      - mnistcnn
      - lstm
strategy:
  - path: "./pybiscus-plugins/strategy"
    modules:
      - flowergeneric
      - fedavgwithaggregator
strategydecorator:
  - path: "./pybiscus-plugins/strategydecorator"
    modules:
      - clipping
      - serverdp
```

Each `path` is added to the Python path at run time, and each listed module is imported. The
core's own modules (such as the `fedavg` strategy) are found without being listed. See
[Plugins](plugins.md) for the categories and what happens when a plugin fails to load.

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
    - its configuration describes the data in `train` / `val` / `test` sections built on
      `pybiscus.ml.datasplit`, which brings the sharing between clients, the held-out validation
      and `max_samples`: see the [integration guide](pybiscus_model_guide.md#data-provider-integration).
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
2. create a file `my_strategy.py`: a Flower strategy is used as it is through
   `pybiscus.flower.flowerstrategy.FlowerStrategyFactory` (Pybiscus' logging added, the aggregation
   left to Flower), with a configuration listing the parameters its Flower class accepts:

```python
from typing import ClassVar, Literal
import flwr as fl
from pydantic import BaseModel, ConfigDict, Field
from pybiscus.flower.flowerstrategy import ConfigFlowerFailuresData, FlowerStrategyFactory

class ConfigMyStrategyData(ConfigFlowerFailuresData):     # fraction_fit, min_*_clients, accept_failures
    server_momentum: float = Field(default=0.9, ge=0, lt=1, description="momentum of the server's steps")

class ConfigMyStrategy(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "My strategy"
    name:   Literal["mystrategy"]
    config: ConfigMyStrategyData
    model_config = ConfigDict(extra="forbid")

class MyStrategyFactory(FlowerStrategyFactory):
    flower_strategy_class = fl.server.strategy.FedAvgM
```

   A strategy of your own derives from a Flower class and keeps its `aggregate_fit` through
   `super()` (see `pybiscus-plugins/strategy/fedavgwithaggregator`): a rewritten aggregation,
   inherited, would turn any subclass into a FedAvg.
3. create the file `$ROOT/my-strategy/__init__.py`:
    - write a function `get_modules_and_configs()` 
    that exports your classes derived from flwr.server.strategy.Strategy
    and their associated configuration classes (derived from pydantic.BaseModel).
    You can follow this template:

```python

from typing import Dict, List, Tuple
from pydantic import BaseModel
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory

from mystrategy.my_strategy import MyStrategyFactory, ConfigMyStrategy

def get_modules_and_configs() -> Tuple[Dict[str, FabricStrategyFactory], List[BaseModel]]:

    registry = { "mystrategy": MyStrategyFactory, }
    configs  = [ConfigMyStrategy,]

    return registry, configs
```
5. of course, add the needed Python libraries using uv
```bash
uv add needed-library1 needed-library2 ...
```

At program launch, the plugin manager prints one line: the number of plugins loaded, and those
skipped because a dependency is missing:

```bash
🧩 [plugins] 29 plugin(s) loaded (details: PYBISCUS_PLUGINS_VERBOSE=1)
```

To check that your plugin is found and registered, set `PYBISCUS_PLUGINS_VERBOSE=1`: the plugin
manager and the registries then print each plugin imported and each class registered, for
instance (excerpt):

```bash
PYBISCUS_PLUGINS_VERBOSE=1 pybiscus server check configs/cifar10_cnn/distributed/without_ssl/server.yml
```

```bash
 🔍 [plugins] Processing category 'data'...
  ✅ 🧩 Successfully imported plugin 'cifar10'
  ✅ 🧩 Successfully imported plugin 'mnist'
 🔍 [plugins] Processing category 'model'...
  ✅ 🧩 Successfully imported plugin 'cnn'
  ✅ 🧩 Successfully imported plugin 'mnistcnn'
📦 Loading module: cifar10
  ✅ Registered: cifar (CifarLightningDataModule)
📦 Loading module: mnist
  ✅ Registered: mnist (MnistLitDataModule)
```

What stops Pybiscus when a plugin fails to load, and what does not, is described in
[Plugins](plugins.md#loading-what-stops-pybiscus-what-does-not).
