# Config files

Config files can be hand-written, but the easy way is to launch a pybiscus agent (for instance `./launch/agent/cli/5000.sh` )
and connect with a browser to its services to produce them at URLs : 
- http://localhost:5000/server/config 
- http://localhost:5000/client/config

More info on the documention of [agent](agent.md) or [session manager](sessionmanager.md)

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

The `cifar` CNN expects 32 x 32 colour images. The `mnist` data plugin goes with `mnist_cnn`
(28 x 28 grey images; `hidden`, `n_classes`, `lr` with Adam): demo `configs/mnist_cnn/distributed/`,
launched by `launch/uv/mnist_cnn/distributed/`, 99 % test accuracy after 3 rounds with 2 clients.
The mnist and cifar plugins download their dataset into its directories on first use; clients
of one machine starting together take turns (a lock per directory): the first one downloads, the
others wait and read the same files.

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

`train.partition.scheme` chooses how the training data is shared between the clients:
`iid` (equal random shares), `dirichlet` (each class spread in proportions drawn from a
Dirichlet(`alpha`) distribution: the smaller `alpha`, the more each client is dominated by a few
classes) or `shards` (examples sorted by class and cut in shards, `shards_per_partition` per
client). The same `seed` on every client gives disjoint shares without coordination.
`pybiscus data partition <client config> [--export <dir>]` shows every client's share and can write
their example indices (`client_<i>_train.txt`, `client_<i>_val.txt`), usable as `train.indices` /
`val.indices`.

The `turbofan` plugin (NASA C-MAPSS engines 52, 62, 2, 64 and 69, shipped with the plugin) predicts
the remaining useful life (RUL) of an engine from a window of its cycles. Its sections choose
engines rather than examples:

```yaml
data:
  name: turbofan
  config:
    window: 20                 # cycles per example, never across two engines
    normalize: true            # features standardized with the train section's engines
    rul_clip: 125              # optional cap on the RUL to predict (unset: none)
    train:
      engines: [52, 62, 2]
      partition: {num_partitions: 2, partition_id: 0, seed: 42}   # whole engines, iid only
    val:
      engines: [64]
    test:
      engines: [69]
```

The normalization statistics come from all the `train.engines`, before partition: every client
computes the same ones, and the server's `train.engines` must be the clients'. Engine 69 lives
longer than the training engines: without `rul_clip`, its RUL often exceeds anything seen in
training (demo `configs/turbofan_lstm/`, campaign `launch/campaign/turbofan_lstm.yml`).
`pybiscus data partition` exports each client's engine numbers.

The `hdfs` plugin (HDFS log sequences, one per CSV line; Deeplog predicts the next event of a
window) shares and holds out **whole sequences**, whose windows overlap:

```yaml
data:
  name: hdfs
  config:
    window: 10
    train:
      file: ${root_dir}/datasets/hdfs_datasets/train.csv
      partition: {num_partitions: 5, partition_id: 0, seed: 42}   # iid only
    val:
      source: holdout          # holdout (fraction, seed) | file (+ file)
      fraction: 0.1
    test:
      file: ${root_dir}/datasets/hdfs_datasets/test.csv    # no default
      format: sessions         # windows | sessions (CSV "seq,label": Deeplog's anomaly F1)
```

`format: sessions` reads labelled sessions, each distinct sequence once with its count, all in
one batch: Deeplog's precision / recall / F1 are computed per batch. `pybiscus data partition`
exports the clients' sequence indices (line numbers of `train.file`).

The server reads only the `test` (and `privacy`) section of the data configuration — turbofan's
also `train.engines`. `server check` warns when its `train` or `val` section differs from the
defaults: those settings have no effect on the server (the agent's form writes every section with
its defaults, which does not warn).

Defaults holding an interpolation (`reporting.basedir: ${root_dir}/experiments`, the data plugins'
`dir`, `root_dir: ${oc.env:PWD}` itself) are resolved like the values written in the YAML: a
configuration may omit them.

An optional `privacy` section (cifar, mnist; server side) gives a privacy evaluation such as a
membership inference attack the examples it attacks: the official train split, never shuffled
nor truncated, so that its example *i* is the example *i* of the exported indices files — which
say which client trained on it.

```yaml
    privacy:
      dir: ${root_dir}/datasets/train/
      batch_size: 32
      max_samples: 1000      # optional: a fixed subset, drawn the same on every run
```

With `max_samples`, the subset keeps the original index of each example
(`pybiscus.ml.datasplit.example_indices`). The server hands the loader to its plugins through
`pybiscus_context[PRIVACY_SET]` (`pybiscus/core/pybiscuscontext.py`, which lists the context keys);
a data plugin provides it with a `privacy_dataloader()` method returning `None` when unset. iSAID
builds it from `dir_privacy`, whose examples must be the ones its indices files number.
The FedMIA attack that uses it is described in [privacy-evaluation.md](privacy-evaluation.md).

### Strategy

```yaml
...
strategy:
  name: "fedavg"
  config:
    min_fit_clients: 2
...
```

#### Server-side differential privacy

The `serverdpfixed` and `serverdpadaptive` decorators (plugin `strategydecorator/serverdp`, over
Flower's `DifferentialPrivacyServerSide*Clipping`) clip each client's update `w_client - w_global`
to a norm C, then add Gaussian noise of standard deviation `noise_multiplier * C / n` to the
aggregated model (n: clients per round). The server is trusted: the noise protects what the
released models tell about each client's data.

```yaml
server_strategy:
  pipeline:
  - name: serverdpfixed          # first: the other decorators then see the noised model
    config:
      noise_multiplier: 0.1
      clipping_norm: 1.0         # adaptive variant: initial_clipping_norm, target_clipped_quantile
  - name: timediffcompute
    ...
```

- Every round logs `dp_clipping_norm`, `dp_noise_stddev`, `dp_clipped_fraction` and, when every
  client takes part in every round (`fraction_fit: 1`), `dp_epsilon` for the configured `delta`
  (Rényi DP of the Gaussian mechanism).
- C: the clients' `weight_drift` under `fedprox` with `proximal_mu: 0` gives the usual size of an
  update.
- The guarantee assumes a plain mean with equal weights: a warning says so around a median, Krum,
  Bulyan, a server optimizer (FedAdam…), FedAvgM or QFedAvg, and when the clients' `num_examples`
  differ (FedAvg weighs by them).
- Refused at check: two DP decorators, or DP with `personalizeclientsfitin` (the update would be
  measured against a model the clients did not receive). Refused at launch: a model with non-float
  state entries (BatchNorm's `num_batches_tracked`), which Flower's clipping cannot scale.
- Few clients make it costly: with 3 clients, z = 1 and C = 1 give a noise of 0.33 per weight and
  stopped cifar10's learning (`launch/campaign/cifar10_serverdp.yml`) for an epsilon of 13 after 5
  rounds. Meaningful central DP needs many clients.


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
### CPU threads

`server_compute_context.num_threads` / `client_compute_context.num_threads` (optional) limit the
CPU threads of PyTorch (`torch.set_num_threads`). Unset, each process takes every physical core,
which makes several clients on one machine wait for each other: give each one about
cores / clients. In a session, the manager sets it for the clients (see the session manager doc).

The server needs no share of its own within a session: it computes (aggregation, global
evaluation) while the clients wait for the next round, and the clients train while it waits, so
it can take every core even on the clients' machine. The manager therefore leaves
`server_compute_context.num_threads` unset. Set it when something else keeps computing on the
server's machine at the same time: several sessions sharing it, or another job. Give it the
cores left to this session:

```yaml
server_compute_context:
  hardware:
    accelerator: cpu
    devices: auto
  metrics_loggers: []
  num_threads: 7   # two sessions on a 14-core machine
```

### Optimizer state between rounds

`client_run.optimizer_state` (`reset` by default, or `keep`): with `reset`, the client creates its
optimizer (and schedulers) again at every round, as in standard FedAvg; with `keep`, it keeps its
state (SGD momentum, Adam moments, scheduler progress) from the previous rounds, although those
were computed on the weights the global model has since replaced.

### Reproducible runs

`server_run.seed` and `client_run.seed` (unset by default: random) seed every random generator of
the process (Python, NumPy, PyTorch) before the model and the data are built: the server's initial
weights and its sampling of the clients, each client's batch order (unless `train.seed` sets it),
dropout and augmentations. Give each client its own seed, or they all draw their batches in the
same order. Two runs with the same seeds start identical and differ only by floating point
rounding (the aggregation sums the updates in their order of arrival, several CPU threads sum in no
fixed order), but training amplifies it: after 5 rounds of 3 local epochs on cifar10, the same run
twice differed by up to 1 point of accuracy. Seeds make runs comparable, not bit for bit
identical.

### Exporting the final model (ONNX)

`server_run.reporting.onnx_export` exports the global model at the end of the session:

```yaml
server_run:
  reporting:
    onnx_export:
      filename: model.onnx
      opset: 18                 # 18 or more with PyTorch's exporter
      post_validation: true     # check the file and compare its outputs with PyTorch's (logged)
      axes:                     # optional: names of the inputs and outputs, batch axis dynamic
      - {name: images, kind: input}
      - {name: logits, kind: output}
```

- The weights go to `model.onnx.data` beside `model.onnx`: keep the two files together.
- Without `axes`, the names and the dynamic axes are deduced from the model and the data; the
  first axis (the batch) is dynamic either way.
- `post_validation` runs `onnx.checker`, then the exported model through onnx's reference
  evaluator (no onnxruntime needed) on a sample, against the PyTorch model computed on CPU in
  float64: a model trained on a GPU would otherwise differ by its TF32 convolutions (2e-4), not by
  the export. It logs the largest difference.

### Reported metrics

The training and evaluation metrics are means over the examples: each batch weighs its size. The
size comes from a `batch_size` key in the step's results if the model gives one, otherwise from
the first dimension of the batch's inputs (or the length of a list of samples). These means are
exact for additive metrics (a mean loss, an accuracy), not for an F1 or an AUC.
