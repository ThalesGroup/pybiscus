# How to use config files

Here are a few hints about how to use and customize the config files (server, client).

## Packages used to handle config

### Pydantic validation

Pybiscus uses Pydantic as a validation process for configuration given by the user. Models, Data, Strategies are provided with Pydantic [BaseModel](https://docs.pydantic.dev/latest/concepts/models/#basic-model-usage) to insure the good use of the different part of Pybiscus.

### OmegaConf

Behind the curtain, Pybiscus uses OmegaConf to deal with loading and saving configuration files. OmegaConf comes with a solver, which in particular allows for value in configuration files like `${oc.env:PWD}`, which allows for more flexibility (avoiding, in the case of key root_dir, to put personal, hard path).

## Description of parts of config files

### Fabric

The keyword `fabric` holds a dictionnary of keywords to use by the Fabric instance. It is used by both Server and Clients. The keywords and their types are simply the one provided by the Fabric API, available [here](https://lightning.ai/docs/fabric/stable/api/generated/lightning.fabric.fabric.Fabric.html#lightning.fabric.fabric.Fabric).

Here is an example from the file `configs/server.yml`:

```yaml
...
fabric:
  accelerator: gpu
  devices:
    - 0
...
```

The keyword `devices` is waiting for either a list of integers (the id of the devices themselves) or an integer (for the number of devices wanted) or the string "auto". To use CPU for instance, you can simply write
```yaml
...
fabric:
  accelerator: cpu
  # devices:
...
```

The keyword `devices` is left intentionnaly commented, as Fabric will automatically find a suitable device corresponding to the choice cpu.

### Models

The keyword `model` holds a dictionnary of keywords to use to instanciate the chosen model. It is used by both Server and Clients.

```yaml
...
model:
  name: cifar
  config:
    input_shape: 3
    mid_shape: 6
    n_classes: 10
    lr: 0.001
...
```

### Data

```yaml
...
data:
  name: cifar
  config:
    dir_train: ${root_dir}/datasets/client1/train/
    dir_val: ${root_dir}/datasets/client1/val/
    dir_test: None
    batch_size: 32
...
```

### Strategy

```yaml
...
strategy:
  name: "fedavg"
  config:
    min_fit_clients: 2
...
```


### Others

For clients, the key cid is to give each client a dedicated integer for designation.

# How to see configuration model

The pydantic2xxx.py command produce a representation of the current pybiscus configuration schema
(dynamically generated as new data and model modules extend it)

it can produce a textual description :

```bash
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py server text
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py client text
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py all text
```

or an html one :

```bash
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py server html
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py client html
 uv run python pybiscus/pydantic2xxx/pydantic2xxx.py all html
```