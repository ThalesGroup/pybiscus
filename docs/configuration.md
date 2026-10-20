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

The same goes for `manager_url`, next to `root_dir` in the server and client configurations: the
address of the session manager, by default `${oc.env:PYBISCUS_MANAGER_URL,http://localhost:5555}`.
The webhooks (logger, metrics logger, model vignettes) default to it (`${manager_url}/webhook/logs`
…): set it once, or export `PYBISCUS_MANAGER_URL`, to send them to another manager. In a session,
the manager sets and locks it in its agents' forms, so that each manager of a hierarchical session
gets the logs and metrics of its own session; a `webhook_url` given explicitly still prevails.

## Description of parts of config files

### Fabric / GPU / hardware description

The keyword `hardware` holds the arguments given to the Fabric instance, on the server and on the
clients. Two of the [Fabric API](https://lightning.ai/docs/fabric/stable/api/generated/lightning.fabric.fabric.Fabric.html#lightning.fabric.fabric.Fabric)'s
arguments are exposed:

- `accelerator`: `cpu`, `gpu` or `auto` (a GPU when there is one);
- `devices`: an integer (the number of devices), or a string: `auto`, or the ids of the devices as
  Fabric reads them (`"0"`, `"0,1"`).

The precision stays Fabric's default (32 bits). On a GPU, convolutions use TF32 by default, which
moves the outputs by about 1e-4: compare models on CPU when the last digits matter.

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

The server reads only the `test` (and `privacy`, `trusted`) sections of the data configuration — turbofan's
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
(in `pybiscus-plugins-privacy-evaluation/`) builds it from `dir_privacy`, whose examples must be the
ones its indices files number.
The FedMIA attack that uses it is described in [privacy-evaluation.md](privacy-evaluation.md).

An optional `trusted` section (cifar, mnist; server side) gives the server a few examples it trusts,
drawn at random from the official train split: the `fltrust` strategy decorator trains on them
every round to judge the clients' updates ([robust-aggregation.md](robust-aggregation.md#fltrust-a-direction-the-server-trusts)).
They must be clean and look like the clients' data; in a simulation they are drawn from the same
split as the clients' shares, as the FLTrust paper's root dataset.

```yaml
    trusted:
      dir: ${root_dir}/datasets/train/
      max_samples: 500       # the default (the paper's: 100)
      seed: 0                # which examples, and the order of their batches
      batch_size: 32         # the clients' batch size: fltrust counts its steps with it
```

The server hands the loader to its plugins through `pybiscus_context[TRUSTED_SET]`; a data plugin
provides it with a `trusted_dataloader()` method returning `None` when unset. `server check`
refuses a pipeline with `fltrust` when the section is missing.

### Strategy

```yaml
server_strategy:
  strategy:
    name: fedavg              # Flower's FedAvg, in the core
    config:
      min_fit_clients: 2      # with min_evaluate_clients and min_available_clients: set by the
      min_evaluate_clients: 2 # session manager to the session's number of clients
      min_available_clients: 2
```

`fedavg` is Flower's FedAvg used as it is: the weights averaged in proportion to each client's
number of examples. `fedavgwithaggregator` (plugin) computes the weights with a
`flowerfitresultsaggregator` plugin instead (`weightedaverage`, the same as FedAvg, or `average`,
every client counting the same). The other Flower strategies come from the `flowergeneric` plugin
(see [Robust aggregation](robust-aggregation.md)). The former `fedavgextended` and `fedavggeneric`
are refused with a message: write `fedavg`; `fedavgextended3` became `fedavgwithaggregator`.

#### FedProx

`fedprox` (plugin `flowergeneric`) sends `proximal_mu` to the clients, which add
`mu/2 * ||w - w_global||^2` to their training: each client is held near the global model during
its local epochs. The term goes straight into the gradients, at no measurable cost; the reported
loss stays the data one. Each client also reports its `weight_drift`, `||w - w_global||` after
training (with `proximal_mu: 0`, the training is FedAvg's and the drift gives the reference).

Measured on cifar10 where FedProx is meant to help (`launch/campaign/cifar10_fedprox_hetero.yml`:
6 clients on dirichlet 0.1 shares, 5 local epochs, 3 clients drawn per round, 20 rounds, 3
seeds), against FedAvg seed by seed:

| mu | mean of the last 5 rounds | worst of the last 10 | spread of the last 10 (std) |
|---|---|---|---|
| FedAvg | 0.418 | 0.264 | 6.3 points |
| 0.001 | −1.3 points (−5.0 to +1.6) | +2.4 (−1.9 to +8.4) | 5.2 |
| **0.01** | **+0.4 (−1.1 to +2.1)** | **+4.1 (+1.3 to +7.3)** | **4.1** |
| 0.1 | −2.5 (−4.3 to −0.6) | +4.0 (−0.6 to +7.5) | 3.6 |

With such shares and partial participation, FedAvg's accuracy swings from round to round (down
to 0.18 after 0.40). `proximal_mu: 0.01` damps the swings by a third and raises the worst rounds,
in every seed, at no cost in accuracy; it does not raise the accuracy itself. 0.1 damps them a
little more but costs 2.5 points; 0.001 does nothing measurable. On mildly heterogeneous shares
with every client in every round (`cifar10_fedprox.yml`), no mu up to 0.01 differed from FedAvg,
and 1 nearly stopped the learning.

#### Server-side differential privacy

The `serverdpfixed` and `serverdpadaptive` decorators (plugin `strategydecorator/serverdp`, over
Flower's `DifferentialPrivacyServerSide*Clipping`) clip each client's update `w_client - w_global`
to a norm C, then add Gaussian noise of standard deviation `noise_multiplier * C / n` to the
aggregated model (n: clients per round). The server is trusted: the noise protects what the
released models tell about each client's data. This is the user-level DP of DP-FedAvg (McMahan et
al., [Learning Differentially Private Recurrent Language Models](https://arxiv.org/abs/1710.06963),
ICLR 2018); the adaptive variant sets C at a quantile of the update norms (Andrew et al.,
[Differentially Private Learning with Adaptive Clipping](https://arxiv.org/abs/1905.03871),
NeurIPS 2021), with the correction of Flower's rule described in
[robust-aggregation.md](robust-aggregation.md#norm-clipping-fedavg-with-bounded-updates).

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
  (Rényi DP of the Gaussian mechanism, composed over the rounds and converted to (ε, δ)-DP:
  propositions 7, 1 and 3 of Mironov, [Rényi Differential Privacy](https://arxiv.org/abs/1702.07476),
  IEEE CSF 2017).
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
- With 20 clients (`launch/campaign/cifar10_serverdp_20clients.yml`, dirichlet shares, 10 rounds,
  three seeds, accuracy at round 10, mean ± std), the noise is divided by 20: FedAvg reaches
  0.363 ± 0.016; z 0.3 costs about a point (0.354) but its epsilon (106) protects little; at epsilon
  20 (z 1) a tight bound learns better than a loose one on every seed, C 0.5 (most clients clipped,
  noise 0.025) 0.291 ± 0.012 against C 1 (noise 0.05) 0.214 ± 0.007, the adaptive bound in between
  (0.232 ± 0.023); at epsilon 9 (z 2, C 0.5) 0.174. Clipping costs less than
  noise: set C near the median update norm, or below it.


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

### Ending a session before its last round

`server_run.num_rounds` is always the most rounds a session runs. `server_run.stopping` lists
criteria tested after each round; the first one met ends the session after that round, which is
reported as at a normal end (final checkpoint, ONNX export):

```yaml
server_run:
  num_rounds: 50
  stopping:
  - name: threshold             # a metric reaches a value
    config: {metric: accuracy, source: test, goal: maximize, value: 0.98}
  - name: patience              # a metric no longer improves (early stopping)
    config: {metric: loss, source: evaluate, goal: minimize, patience: 3, min_delta: 0.001}
  - name: maxduration           # the rounds have lasted this long
    config: {minutes: 120}
```

- `source` is one of the manager's curves: `test` the server's evaluation on its test set,
  `evaluate` the clients' evaluation, `fit` their training metrics. `metric` is a name the strategy
  reports (`loss`, `accuracy`, `f1score`…). A metric missing at a round is logged once, with the
  available ones, and never ends the session.
- The session manager's page shows `k/N ⏹` and the reason (`test accuracy 0.981 ≥ 0.98`), or
  `N/N 🏁` when every round was run. The server can also be stopped by hand after its round: the
  manager's *⏹ stop after round* button, or `kill -USR1 <pid>` ([cli.md](cli.md)).
- In a hierarchical session, only the top level decides: a lower level refuses `stopping` at
  `check`, since it runs the rounds of its upper level, and ends with it, after the same round
  ([hierarchical-session.md](hierarchical-session.md#ending-before-the-last-round)).
- The criteria are plugins (the `stoppingcriterion` category, [plugins-reference.md](plugins-reference.md#stopping-criteria)):
  `should_stop(server_round, history)` gets Flower's `History` of the session and returns the
  reason to stop, or `None`.

### Rounds at fixed times

`server_run.schedule` runs the rounds at deadlines rather than back to back, so that each one
trains on the data arrived since the previous one ([below](#data-arriving-between-rounds)):

```yaml
server_run:
  num_rounds: 30                # the rounds counted: the skipped ones are not
  schedule:
    cron: "0 2 * * *"           # every day at 02:00; or every: 1h30min
    timezone: Europe/Paris      # the machine's zone if unset
    start: now                  # the first round at once; deadline: it waits too
  stopping:
  - name: maxduration
    config: {minutes: 43200}    # 30 days, waits included
```

- The server waits between two rounds; Flower announces `[ROUND n]` when the round starts, and the
  server logs `next round at …` beforehand. A deadline missed, the previous round having lasted
  longer than the period, is not made up for (`pybiscus schedule preview` shows the deadlines,
  [cli.md](cli.md#checking-a-schedule)).
- A round in which no client trained (none had new data: every one left it) is **skipped**: no
  evaluation, no stopping criterion tested, and it does not count among `num_rounds`. Flower's
  round numbers, used in the logs and the metrics, go on over it: the manager's page shows the
  rounds counted (`🗓️ gui rounds_done=k/N` in the server's log). Without a schedule, a round all
  clients failed still counts, so that `num_rounds` bounds a session whose clients keep failing.
- `maxduration` depends on the clock only: it is also tested on the skipped rounds and while the
  server waits, so that a session left without new data ends. The other criteria look at the
  rounds actually run. The *⏹ stop after round* button and `kill -USR1` end the wait at once.
- The connections to the clients stay open during the waits, kept alive by gRPC (Flower's
  keepalive, every 3 min 30 s): checked with a 5 min wait on one machine; a firewall or a NAT that
  cuts idle connections sooner may still end a long wait, and a client lost is not taken back.
- A lower level of a hierarchical session refuses `schedule`: it runs its upper level's rounds.
- Each round of a long session keeps the state of the server, and its connections to the
  clients. The manager can instead launch a session again at each deadline, each one starting
  from the previous one's final weights ([sessionmanager.md](sessionmanager.md#repeated-sessions)).

### Data arriving between rounds

New examples may arrive while a session runs, or between two sessions: the logs of the day, new
captures:

```yaml
client_run:
  refresh_data: true            # the data module reads its data again before each round
data:
  name: hdfs
  config:
    train:
      directory: ${root_dir}/logs   # a lot per file, read in the order of the names
      lots: new                     # only the lots not trained on yet
```

- Without `refresh_data`, a client reads its data once, when it starts. With it, before each fit,
  the data module reads its data again: all of it by default (`setup("fit")` again), or only what
  is new for a module that supports it, such as `hdfs` with `train.lots: new`.
- An incremental module remembers, per client, the last data it trained on, in
  `.pybiscus-cache/data-cursors/` of the directory the client runs from, across sessions: a
  client restarted for a new session does not train on its old lots again. The position moves on
  after a successful fit only, so a round that fails leaves its data to the next one. Delete the
  file to read everything again.
- A client with no example to train on (nothing new) **leaves the round**: the server counts it
  among the round's failures and logs why (`a client left the round: no new data: client 1 has no example to train on…`). With
  `accept_failures: true` (the default) the round goes on with the others; with no client left the
  global model stays as it was. Strategies that refuse any failure (the server-side adaptive
  clipping of DP) skip such rounds.
- `hdfs` shares out (`partition`) and holds out (`val.source: holdout`) each lot on its own: drawn
  on the whole of a growing directory, the earlier lots' shares would change at each new lot.
  The reports of each round carry `fit_data_lots_<cid>`, the number of lots the client read.
- `pybiscus server launch … --weights-path latest` starts from the final weights of the last
  session of the reporting `basedir` that saved them (`save_on_train_end`), or from random weights
  if none did yet: the next session of a series goes on from where the previous one ended.
  `server_run.weights_path` sets it in the configuration (`latest` or a file); the option wins.
- `server_run.stop_without_new_data: true` ends the session at a round in which no client
  trained, that round not counted: a session launched while nothing new has arrived ends at once.
- `pybiscus schedule preview --every 1h` or `--cron "0 2 * * *" --timezone Europe/Paris` shows
  the next deadlines of a schedule ([cli.md](cli.md#checking-a-schedule)), before setting
  `server_run.schedule` ([above](#rounds-at-fixed-times)).

### Files of the reporting directory

The server, its metrics loggers and the strategy decorators write into one reporting directory
(`server_run.reporting.basedir`, a subdirectory per session). `check` refuses a configuration
where two of them would write the same file, or one in a directory another owns (TensorBoard's,
W&B's `wandb/`): the overwritten file would otherwise be found only after the session.

The usual case is a decorator used twice in the pipeline, to save the weights before and after a
transformation. Give each instance its own `tag`, a subdirectory of its files:

```yaml
server_strategy:
  pipeline:
  - name: saveserverfitparams
    config: {tag: before}       # rounds/round_<n>/before/server_aggregated_fit_parameters.npz
  - name: clipping              # any decorator transforming the aggregate
    config: {...}
  - name: saveserverfitparams
    config: {tag: after}        # rounds/round_<n>/after/server_aggregated_fit_parameters.npz
```

The plugins writing files take a `tag`: the decorators `saveserverfitparams`, `saveclientsfitin`,
`saveclientsfitres`, `visualizemodellayers`, `fedmiaprivacyevaluation`, and the result modifier
`clientwatermarking` (in `personalizeclientsfitin`). The check covers the server only for now. For a plugin author: a config
inheriting `ReportingOutputs` (or `TaggedReportingOutputs`, `pybiscus/core/reportingoutputs.py`)
declares its outputs in `reporting_outputs()` and builds their paths with `output_path(name,
round=..., cid=...)`, so that the check and the writing use the same path.

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
