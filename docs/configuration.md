# Config files

Config files can be hand-written, but the easy way is to launch a pybiscus agent (for instance `./launch/agent/cli/5000.sh` )
and connect with a browser to its services to produce them at URLs : 
- http://localhost:5000/server/config 
- http://localhost:5000/client/config

More info on the documention of [agent](agent.md) or [session](session.md)

# Details about config files

Here are a few hints about how to use and customize the config files (server, client).

## Packages used to handle config

### Pydantic validation

Pybiscus uses Pydantic as a validation process for configuration given by the user. Models, Data, Strategies are provided with Pydantic [BaseModel](https://docs.pydantic.dev/latest/concepts/models/#basic-model-usage) to insure the good use of the different part of Pybiscus.

### OmegaConf

Behind the curtain, Pybiscus uses OmegaConf to deal with loading and saving configuration files. OmegaConf comes with a solver, which in particular allows for value in configuration files like `${oc.env:PWD}`, which allows for more flexibility (avoiding, in the case of key root_dir, to put personal, hard path).

## Description of parts of config files

### Fabric / GPU / hardware description

The keyword `hardware` holds keywords to use by the Fabric instance. It is used by both Server and Clients. The keywords and their types are simply the one provided by the Fabric API, available [here](https://lightning.ai/docs/fabric/stable/api/generated/lightning.fabric.fabric.Fabric.html#lightning.fabric.fabric.Fabric).

The keyword `devices` is waiting for either a list of integers (the id of the devices themselves) or an integer (for the number of devices wanted) or the string "auto".

Here is an example from a server configuration:

```yaml
...
server_compute_context:
  hardware:
    accelerator: auto
    devices: auto
...
```

And anoter one from a client configuration:

```yaml
...
client_compute_context:
  hardware:
    accelerator: auto
    devices: auto
...
```

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
    train:
      dir: ${root_dir}/datasets/train/
      batch_size: 32
      # optional: this client's share of the training examples
      partition:
        num_partitions: 2
        partition_id: 0
    val:
      source: holdout          # official (the official test split) | holdout | indices
      fraction: 0.1
    test:
      dir: ${root_dir}/datasets/test/
    num_workers: 0
...
```

Each of `train`, `val` and `test` also takes `shuffle` and `drop_last` (defaults: the training
set is shuffled and drops its last incomplete batch, the evaluation sets do neither); `train`
takes a `seed` (order of the batches) and an `indices` file (example indices to train on);
`val` with `source: indices` takes an `indices` file.

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

The pydantic2xxx.py command generates dynamically a representation of the current pybiscus configuration schema

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