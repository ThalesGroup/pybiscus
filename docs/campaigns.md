# Campaigns: comparing strategies on short federated runs

`launch/campaign/strategy_campaign.py` runs the same federated setting with several variants (a
strategy, decorators, malicious clients...), each as a real session on the machine — a server and
its clients as separate processes — and prints a table of the test metric round by round. It is
how the results of [Robust aggregation](robust-aggregation.md) and
[Privacy evaluation](privacy-evaluation.md) were measured.

## Running one

From the repository root:

```bash
uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_strategies.yml
uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_strategies.yml --only "Fed"
```

`--only` runs the variants whose label starts with the given text.

For every variant (and every seed, see below), the tool copies the campaign's server and client
configurations, applies the variant to them, shares the training data between the clients, starts
the server and the clients on the campaign's port, and waits for the server to finish. Each run's
line is printed as soon as it ends.

Results go to `<output>/<start date and time>/` (`experiments/campaigns/` by default):
- one directory per run, named after its label and seed: the generated `server.yml` and
  `client_<i>.yml`, the processes' logs (`server.log`, `client_<i>.log`) and the server's reports
  (`experiments/`: `server_logs.txt`, `metrics.txt`...);
- `results.md`: the tables.

**Before running one**
- The campaign's `port` must be free: the tool refuses to start otherwise.
- Do not run it next to a live session: it takes every core (`threads_per_client: auto`) and, with
  `accelerator: auto`, the GPU, and slows both down.
- Each campaign file says in its header how long it takes.

## The campaign file

```yaml
server_config: configs/cifar10_cnn/distributed/without_ssl/server.yml   # base configurations,
client_config: configs/cifar10_cnn/distributed/without_ssl/client_1.yml # copied for every run
output: experiments/campaigns                   # default
plugin_manifests: [launch/campaign/test-plugins-conf.yml]   # optional: test-only plugins

clients: 7                 # clients of every run
rounds: 5
local_epochs: 3            # optional: server_run.clients_fit_local_epochs
port: 3399                 # the Flower server of each run
threads_per_client: auto   # optional: physical cores / clients (default), a number, or 0 for none
timeout: 1800              # optional: seconds per run (default 1800)
seeds: [1, 2, 3]           # optional: every variant once per seed
seed_partitions: false     # optional: also draw the data shares again with each seed

client_data:               # merged into every client's data.config
  train:
    partition: {scheme: dirichlet, alpha: 0.5, seed: 42}
  val: {source: holdout, fraction: 0.1}
server_data:               # merged into the server's data.config
  test: {max_samples: 2000}

variants:
  - label: FedAvg
    strategy: {name: fedavg, config: {}}
  - label: clipping, 1 attacker
    reference: FedAvg                        # optional: paired difference to this variant
    strategy: {name: fedavg, config: {}}
    pipeline: [{name: clipping, config: {mode: median, median_factor: 1.5, reject_factor: 1.7}}]
    client_overrides:                        # optional: per client, by number (0 .. clients - 1)
      0: {flower_client: {alternate_client_class: {name: byzantine, config: {attack: sign_flip}}}}
```

What the tool sets in the copied configurations:

| key | effect |
|---|---|
| `clients` | the number of client processes; each gets `client_run.cid` = its number, and when the client data has a `train.partition`, `num_partitions` = `clients` and `partition_id` = its number |
| `rounds`, `local_epochs` | `server_run.num_rounds`, `server_run.clients_fit_local_epochs` |
| `port` | the server listens on `[::1]:<port>`, the clients reach it there |
| `threads_per_client` | each client's `client_compute_context.num_threads` |
| `client_data`, `server_data` | merged key by key into `data.config` (a value given here replaces the base one) |
| `plugin_manifests` | appended to the default plugin manifest (`PYBISCUS_PLUGIN_CONF_PATH`) for the runs: test-only plugins, such as the `byzantine` client, never appear in a real session's forms |
| variant `strategy` | `server_strategy.strategy`; its `min_fit_clients`, `min_evaluate_clients` and `min_available_clients` default to `clients` (every client in every round) unless the variant sets them |
| variant `pipeline` | put in front of the base configuration's pipeline: closest to the strategy, so that the base decorators (saved parameters, timings) see what the variant's produce |
| variant `client_overrides` | merged last into the given clients' configurations, e.g. to make some of them malicious; `{work}` in a string becomes the run's directory (a shared directory of its own, without files left by an earlier run) |
| `seeds` | `server_run.seed` = the seed, client i's `client_run.seed` = 1000 x seed + i, a byzantine client's `seed` = the seed (unless set); with `seed_partitions: true`, the partition's `seed` too |
| `output` | where the start-dated directory goes |

The base configurations are left unchanged: everything is written into each run's directory.

## Reading the results

`results.md` first holds one line per run: the test metric of every round (the model's main metric:
accuracy, or the loss for a regression), the time of the last round, and the run's status (`ok`, a
non-zero exit of the server, `timeout`, or the number of tracebacks in the logs).

With `seeds`, a second table gives, per variant, the mean ± standard deviation over the seeds, and
for a variant with a `reference`, its difference to that variant at the last round, **seed by seed**
(mean ± standard deviation, and range). Most of the spread between two runs comes from the seed
itself — the initial weights, the batch orders, the sampled clients — and is shared by every
variant: the paired difference cancels it and is far steadier than two means.

Even paired, a difference below about one point means nothing: the same run repeated with the same
seed differs by up to one point after a few rounds, floating point rounding being amplified by
training (see [Reproducible runs](configuration.md#reproducible-runs)).

## Existing campaigns

All on the repository's demos; each file's header says what it measures, with how many clients,
and how long it takes.

| campaign | what it measures | results |
|---|---|---|
| `cifar10_strategies.yml` | the server strategies compared (FedAvg, FedAdam, FedYogi...) | DEVLOG |
| `cifar10_robust.yml` | robust aggregations against sign-flipping attackers, iid shares | [robust-aggregation.md](robust-aggregation.md#results-cifar10-7-clients-iid-shares-3-local-epochs-5-rounds) |
| `cifar10_robust_dirichlet.yml` | the same on heterogeneous (dirichlet 0.5) shares | [robust-aggregation.md](robust-aggregation.md#heterogeneous-shares-dirichlet-05) |
| `cifar10_clipping_dirichlet.yml` | bounding the updates' norm, dirichlet shares | [robust-aggregation.md](robust-aggregation.md#norm-clipping-fedavg-with-bounded-updates) |
| `cifar10_alie_dirichlet.yml` | the defenses against colluding ALIE attackers | [robust-aggregation.md](robust-aggregation.md#a-discreet-colluding-attack-alie) |
| `cifar10_alie_z_sweep.yml` | ALIE's z swept, 3 seeds | [robust-aggregation.md](robust-aggregation.md#sweeping-z) |
| `cifar10_clipping_reject_alie.yml` | the clipping defense's rejection threshold against ALIE | [robust-aggregation.md](robust-aggregation.md#rejection-threshold) |
| `cifar10_safeguard_iid.yml` | the `safeguard` defense on iid shares | [robust-aggregation.md](robust-aggregation.md#on-iid-shares) |
| `cifar10_directions_alie.yml` | the updates' directions under ALIE (`log_directions`) | [robust-aggregation.md](robust-aggregation.md#discreet-attackers-what-the-norm-cannot-see) |
| `cifar10_serverdp.yml` | server-side differential privacy against FedAvg | [configuration.md](configuration.md#server-side-differential-privacy) |
| `cifar10_fedmia.yml` | FedMIA membership inference (then the analyser) | [privacy-evaluation.md](privacy-evaluation.md) |
| `cifar10_fedprox.yml` | FedProx's mu against FedAvg, 3 clients, short | [configuration.md](configuration.md#fedprox) |
| `cifar10_fedprox_hetero.yml` | FedProx where it is meant to help: dirichlet 0.1, 5 local epochs, 3 of 6 clients per round, 20 rounds, 3 seeds | [configuration.md](configuration.md#fedprox) |
| `turbofan_lstm.yml` | the LSTM regression on the turbofan engines (test MSE: lower is better) | [configuration.md](configuration.md#data) |

`test-plugins-conf.yml` is not a campaign: it declares the test-only plugins (the `byzantine`
client) that the robustness campaigns add through `plugin_manifests`.
