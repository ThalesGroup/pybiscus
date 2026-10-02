# Changelog

## [Unreleased] (future 0.8.0)

From `dem_bx_0326` (2026-03-20) to the `rolling` branch: Pybiscus' functional scope grows — every
Flower server strategy, defenses against malicious clients, privacy evaluation, data shared
between clients — and the sessions become reliable and reproducible.

### Breaking changes

* **Data configuration in sections**: the data plugins (cifar10, mnist, hdfs, turbofan,
  randomvector, vector, iSAID's privacy set) take `train`, `val`, `test` (and `privacy`) sections,
  each with its own directory or source and loader options. The former flat fields
  (`dir_train`, `batch_size`, `num_samples`, `data_train_indices_path`...) are refused with
  their new location.
* **Strategy names**: the four FedAvg are merged into `fedavg` (Flower's FedAvg, in the core);
  `fedavgextended` and `fedavggeneric` are refused (write `fedavg`), `fedavgextended3` became
  `fedavgwithaggregator`, whose `flower_fit_results_aggregator` is now `aggregator`.
* **Network exposure**: the agents and the session manager listen on the loopback by default;
  beyond it they require access tokens, and they refuse cross-site requests (`X-Pybiscus`
  header). The session manager gains `--host`.
* **Python 3.12** is required; `flwr < 2`.
* The agent's `/exit` and `/shutdown` routes, which did not work, are removed.
* FedAvg weighs the clients by their number of examples (it used their number of batches), and
  metrics are averaged over the examples: results differ from earlier versions.

### Strategies and robustness

* `flowergeneric` plugin: FedAvgM, FedProx, FedAdam, FedYogi, FedAdagrad, FedMedian,
  FedTrimmedAvg, Krum, Bulyan, QFedAvg, FaultTolerantFedAvg, Flower's classes used as they are
  with Pybiscus' logging; hyperparameters tuned on measurements.
* FedProx's proximal term in the clients' training (as a gradient, at no cost); measured: with
  heterogeneous data and partial participation, `proximal_mu: 0.01` damps the round-to-round
  swings by a third.
* `robustness: safeguard` in the server strategy (and in the session form): the `clipping`
  decorator (updates clipped to 1.5 x the median norm, those above 1.7 x left out of the round),
  measured on iid and heterogeneous shares; `log_directions` for diagnosis.
* Server-side differential privacy decorators (fixed and adaptive clipping; Flower's adaptive
  clipping corrected).
* FedMIA privacy evaluation decorator and its analyser (under development), iSAID data and
  FasterRCNN model plugins (from PR #44).
* Test-only `byzantine` client (sign flip, scaling, noise, colluding ALIE) for the campaigns.
* `docs/robust-aggregation.md`: what each defense stops, and what it does not (attackers that
  stay within the honest clients' range).

### Sessions and web applications

* The session manager sets the strategy's minimum numbers of clients to the session's clients;
  `min_clients` sets another number, after a confirmation stating the risk.
* Session-wide data partition (iid, dirichlet, shards) and validation holdout; each client's CPU
  threads shared on its machine.
* Session presets are set in every option of the forms' unions, so that switching the strategy
  or the data plugin keeps them.
* Every field of the forms is described on hover; enum values one by one.
* Agent forms: chips and radial menu for long option lists, compact list view, vertical tabs for
  unions, display settings panel, lists with default items; session manager reshaped, agents
  running page, hardened agent/manager protocol, session relaunch, charts of any metric.
* `3frames.html` shows the server agent and 1 to 9 client agents in one page (grid, focus and
  single layouts), for sessions tested on one machine.

### Data, models and runs

* `pybiscus data partition [--export]`; dirichlet and shards partitions; hdfs and turbofan data
  rebuilt on sections; iSAID and the privacy set.
* `mnist_cnn` model (the mnist data plugin had none) with its demo.
* `server_run.seed`, `client_run.seed`: reproducible runs.
* `client_run.optimizer_state` (reset or keep between rounds); learning rate schedulers applied;
  every `configure_optimizers` form supported; fit metrics per local epoch.
* ONNX export: declared axes work, `post_validation` checks the exported model.
* Datasets downloaded under a lock: clients starting together on one machine no longer fail.
* The W&B metrics logger rewritten so that it runs.
* Campaign tool (`launch/campaign/strategy_campaign.py`): variants, seeds, paired differences;
  documented in `docs/campaigns.md`.

### Verification and containers

* `launch/ci/smoke.sh` replays the basic validation and exits non-zero on failure: `check` on every
  server and client configuration of `configs/`, a short federated run (mnist, CPU), the build of
  the two container images and the same run in containers.
* The container build scripts work from the repository root (they only worked from
  `container/`); the agent starts in its container.
* The container launch scripts reserve the first GPU (`--gpus device=0`; they asked for the
  second one).

### Fixes

* Sessions started with the form's default strategy could end without any training: rounds were
  cancelled until every client was connected.
* The manager's metrics panel stayed empty with the forms' defaults.
* Server initial parameters built from the model's state, as on the clients; cifar10 and mnist
  validation and test evaluate every example; invalid configurations reported to the agent by a
  dedicated exit code; client overrides applied alike in `check` and `launch`.
* Plugin loading: failures reported instead of exiting, shadowing, key/name pairing, re-entrancy
  and collisions detected.

### Dependencies

* Vulnerable dependencies bumped (GitPython, aiohttp, Pillow, onnx...), lightning 2.6.6, torch
  2.13. `cryptography` stays below 47, pinned by flwr.

### Known limits

* iSAID and FasterRCNN were not run on real data for this release; FedMIA is under development.
* GPU access from the containers was not tested (the images were, on CPU).

## [Version 0.7.0]

The architecture introduced in 0.6.0 matures; the use of Flower stays the same (FedAvg); the web
applications grow into a session manager driving its agents.

### Sessions and web applications

* Mixed sessions: every agent, server included, registers dynamically with the session manager,
  with extended registration parameters (one configuration file per agent).
* The session manager produces the forms' presets and hands them to every agent; it presets each
  client's `cid`.
* Server form: configuration cache, pin and blank buttons, origin indicator; execution enabled
  once the configuration is checked; session routes under `/pybiscus-session`.
* Agents' logs shown by the manager; agents' states drawn from the logs (colour codes), round
  durations, metric differences between rounds, fit/test/eval accuracies; callbacks stopped at
  the end of a session; manager pages merged into one grid.
* Client and server theming, dark and light modes.
* Relay: a server that writes its aggregated results to files, and a client that replays them
  instead of training.

### Strategy decorators and personalization

* Result modifiers (plugins) and the decorator that personalizes what each client is sent
  (example: result multiplication); option to save the clients' fit results.
* Client watermarking: one fingerprint per client, checkpoint saving.
* Model layers' vignettes posted to the session manager (`visualize_model_layers`).
* Strategy decorator pipeline refactored (consistent files and naming); utilities to build
  checkpoints from saved `.npz` parameters.

### Models, data and runs

* `server_run.clients_fit_local_epochs` (local epochs were fixed to 1).
* The test loop uses the model's `test_step`; models may declare a signature per mode
  (`signatures(mode)`).
* The Pybiscus context exposes the model and its device to the plugins, on the clients too.
* hdfs data and Deeplog model fixes; TensorBoard filters out non-numeric values.

### Plugins

* Plugin loading errors handled (stop on error); registries split into
  `pybiscus/plugin/registries/`.
* Documentation: plugins developed in separate projects (multi-project mode), session management.

## [Version 0.6.0]

The architecture becomes plugin-based, and the first web applications (the Pybiscus agent and
the session manager) appear.

### Breaking changes

* Project managed with **uv** (Poetry dropped); the source tree `src/` became the `pybiscus`
  package; commands as uv scripts (`pybiscus`, `pybiscus_agent`, `session_manager`).
* Configuration overhaul: former configuration files must be converted (the agent generates
  them); the strategy `FabricStrategy` became `fedavg`.
* Data and models moved out of the core into plugins.

### Plugin architecture

* Each data, model or strategy module exports `get_modules_and_configs()`, discovered and
  registered at start-up; plugins live in `pybiscus-plugins/`, listed in
  `pybiscus-plugins-conf.yml` (`PYBISCUS_PLUGIN_CONF_PATH`, several manifests, `pybiscus.env`).
* Pluggable categories: data, models, strategies (`FabricStrategyFactory`), strategy decorators
  (pipeline; time and metric differences as examples), clients (alternate client class),
  loggers, metrics loggers, fit result aggregators (`fedavgextended3`).
* Sanity checks of the plugins' configurations; usage with external plugins.

### Web applications

* Pybiscus agent (first named "node", REST API): server and client configuration forms generated
  from the Pydantic models, check and launch, configuration saving, registration with the session
  manager from its page; also in a container.
* Session manager: a session's server and clients configured together (network parameters set
  and locked), server logs and metrics shown live through webhooks.
* Forms: optional fields as checkboxes, foldable items and two-level menu, lists and
  dictionaries, tooltips from the models' docstrings, core/plugin origin marker, modernized CSS.

### Logging and reporting

* Configurable loggers (console, webhook) instead of the console; a list of metrics loggers
  (TensorBoard, webhook, W&B — untested then); the server's logs and metrics saved in its reporting directory
  (`server_logs.txt`, `metrics.txt`).
* Reporting section: time-stamped directory, final weights saving, ONNX export (axes from the
  configuration or deduced).
* The server can start from saved weights.

### Models and data

* Turbofan data and LSTM regressor; linear regression and random vector data; MNIST data (no
  model for it yet); noop model.

### Containers and security

* Podman first, Docker compatible; images for Pybiscus and the agent; SSL between server and
  clients, with scripts to generate the CA and certificates; launch scripts per use case
  (`launch/uv`, `launch/container`).

### Documentation

* Architecture schema, plugin development, step-by-step model and data integration guide, agent
  and session manager.

## [Version 0.5.0]

* Renaming the commands of client and server parts. Improving the help printed by Typer.
* Adding a new check command for both Server and Client sides in order to possibly check before-hand the validity of the provided configuration file.
* **REFACTO**: the main commands of the pybiscus app are now located in src/commands. For instance, the previous version of `src/flower/client_fabric.py` is split into the Typer part src/commands/app_client.py and the new version of `src/flower/client_fabric.py`. This helps structure the code into more distinct block.
* The Unet3D Module comes now with a better Dice Loss and a Dice metric instead of the Accuracy (not suitable in the context of segmentation of 3D images).
* Small change on the `weighted_average` function, to take care of the change of keywords.
* **NEW FEATURE**: using Trogon to add a Terminal User Interface command to the Pybiscus app. This helps new users to browse through help, existing commands and their syntax.

## [Version 0.4.0]

* the Server has now the possibility to save the weights of the model at the end of the FL session.
* add the possibility to perform a pre train validation loop on the Client. This feature allows to perform one validation loop, on the validation dataset holds by the client, of the newly sent, aggregated weights.
* updating the Lightning version needed: not "all" anymore, just "pytorch-extra" in order to have way less dependencies to install and check.

* **NEW FEATURE**: using Pydantic to validate ahead of time the configuration given to the CLI:
    - data config validation
    - model config validaton
    - server config validation
    - client config validation
    - Fabric config validation
    - Streategy config validation
* adding some documentation for the use of config files.
* updating the documentation on various classes and functions.

## [Version 0.3.3]

* moving loops_fabric.py into ml directory (a better place)
* getting rid of load_data_paroma, amd replaces it by direct use of LightningDataModule.
* updating config files accordingly
* moving logging of evaluate function to evaluate inside FabricStrategy; more coherence with aggregate_fit and aggregate_evaulate.
* upgrading the config for local training with key 'trainer', making all Trainer arguments virtually available
* adding a constraint on deepspeed library due to some issues with the installation of the wheel. Issue with poetry? In poetry, version is 0.9.0 but in installing the wheel built by poetry, it is 0.11.1...
