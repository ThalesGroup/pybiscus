# Changelog

## Unreleased

### Agent pages

* Registration and waiting pages in the manager's dark style, without animated particles or emojis;
  registration fields grouped (connection, this agent, location on the map); the session token field
  now spans the form's width (a password field missed the input style, and its hint was cut).
* Run monitor: the agent's name and site as title; the status banner coloured by the run's status (a
  success used to show in red).
* Configuration forms: field names as plain text next to their value instead of framed badges; an
  optional field shows *optional* instead of a red ❓; Check is the primary action, Execute stays
  outlined until a check passes, Save / Pin / Blank are secondary, the config's origin is a badge;
  buttons named Check, Execute, Save to disk, Pin, Blank. The session form is titled "Pybiscus session
  configuration". The attributes the YAML is read from are unchanged.
* Check: each validation error is shown in red under its field (or on the block it is about) and the
  form opens the section of the first one; it used to show only "Check failure", the details being in
  the agent's console. `pybiscus server|client check` writes the errors as JSON in the file named by
  `PYBISCUS_CHECK_ERRORS_FILE`, set by the agent.
* Section menu: after a check, each section shows the number of its errors or a ✓; the mark goes when
  the section is changed.
* Readable labels: each field shows its `title`, or its key spelled out (abbreviations expanded,
  `num_`/`n_`/`nb_` read "Number of"), with the YAML key under it in small type; the section menu
  shows the label alone. A few titles added (local epochs per round, one directory per session,
  q (fairness)...). The option names, which the presets and pins compare, are unchanged.
* A check, a save or a pin run during the 600 ms switch between two options of a union read the
  whole union as missing (`data: Field required`): the chosen option is now recorded at the click,
  only its display waits.

### Robustness tests

* ALIE at the paper's proportion of attackers, 5 of 20 clients, z 1
  (`launch/campaign/cifar10_alie_20clients.yml`, six defenses, 3 seeds): 5 client-side colluders do
  nearly the omniscient attacker's harm, steady but small (FedAvg −0.9 point, median −2.3, Bulyan
  −4.0); Krum, f 5, does not learn on dirichlet shares among 20 clients.

## [Version 0.12.0]

Since `version0.11.0` (2026-10-18): Flower 1.40, and the dependencies with known vulnerabilities
updated; no change of behavior.

### Dependencies

* Flower 1.27.0 → 1.40.0 (`flwr>=1.40.0`): its DP functions moved to
  `flwr.supercore.differential_privacy`, which the `serverdp` plugin now imports; Pybiscus stays on
  Flower's legacy API (`start_server`, `start_client`), unchanged in 1.40.
* Known vulnerabilities fixed: `cryptography` 46.0.7 → 50.0.2 (no longer capped by Flower:
  GHSA-537c-gmf6-5ccf and three others), `fsspec` 2026.2.0 → 2026.9.0 (GHSA-27vj-qcqg-25rc, high:
  code execution through `ReferenceFileSystem` templates), `mako` 1.4.1 → 1.4.3
  (GHSA-5639-2j2p-m4mx), `multidict` 6.7.1 → 6.9.1 (GHSA-54p9-h82j-f925), `werkzeug` 3.1.6 →
  3.1.9 (GHSA-g6x2-hccm-hh4m); `pip-audit` finds none left in `uv.lock`.

## [Version 0.11.0]

Since `version0.10.0` (2026-10-17): two more defenses against malicious clients, FLTrust (trusted
examples on the server) and FoolsGold (clients that look alike), measured against new attacks of the
test clients — poisoned labels, ALIE by attackers who know the honest updates —; campaigns checked
in seconds, without running them.

### Robustness

* FLTrust (Cao et al., NDSS 2021): the `fltrust` strategy decorator trains the global model on a
  few trusted examples every round and weighs each client by the cosine similarity of its update to
  the server's (0 when negative), its update scaled to the median client norm; over `fedavg` or
  `fedprox`. Measured (`launch/campaign/cifar10_fltrust.yml`): it leaves out sign flippers every
  round and lowers omniscient ALIE at z 2, but not at the paper's z, at a cost of 3 points without
  attacker; `safeguard` stays the advice.
* Data: an optional `trusted` section (cifar, mnist), examples drawn from the train split that the
  server trains on (`pybiscus_context[TRUSTED_SET]`).
* Server configuration: a decorator may name the strategies it works over (`PYBISCUS_STRATEGIES`)
  and the data sections it needs (`PYBISCUS_DATA_SECTIONS`), refused at check otherwise.
* FoolsGold (Fung et al.): the `foolsgold` strategy decorator weighs down the clients whose history
  of updates looks like another client's; over `fedavg` or `fedprox`. Measured
  (`launch/campaign/cifar10_foolsgold.yml`, `cifar10_foolsgold_iid.yml`): it leaves out colluders
  sending the same update, but costs 11 points without attacker on dirichlet shares and does not
  see label flippers: not advised in these settings.

### Robustness tests

* The worst case of ALIE: the `omniscientalie` strategy decorator (test manifest only) replaces the
  updates of the clients flagged byzantine by mean − z · std of the honest updates of the round,
  as attackers who know them would; campaign `launch/campaign/cifar10_alie_omniscient.yml` (six
  defenses, the paper's z and z 2, 3 seeds) and its results in `docs/robust-aggregation.md`.
* On iid shares, honest clients' updates are as alike as 0.99 (cosine to the closest other):
  rejecting near-duplicates by a fixed threshold would reject honest clients, and is not
  implemented; ALIE does almost no harm there (campaign `launch/campaign/cifar10_directions_iid.yml`).
* Data poisoning: `attack: label_flip` of the `byzantine` client trains on the labels
  l → num_classes − 1 − l and sends that update unchanged; campaign
  `launch/campaign/cifar10_label_flip.yml`: the norm-based `safeguard` sees nothing (−11.6 points,
  as FedAvg), FLTrust ends highest under attack (−6.3 points from its own 0.372).
* FLTrust's trusted examples: 500 do better than 100 (−2.2 points without attacker, +4.4 over
  FedAvg against label flippers), 2000 no better than 500
  (`launch/campaign/cifar10_fltrust_trusted_size.yml`): the default `trusted.max_samples` is 500.
* FLTrust on iid shares costs nothing without attacker (+0.2 point), leaves the sign flippers out
  and halves the label flippers' harm (`launch/campaign/cifar10_fltrust_iid.yml`).

### Tools

* Campaigns: a variant may set its own `server_data` (merged after the campaign's).
* `strategy_campaign.py --check` validates the configurations of every run of a campaign, as
  `server check` and `client check` do, without running them; `launch/ci/smoke.sh check` runs it
  on every campaign of `launch/campaign/`.

### Documentation

* References for the defenses and attacks measured (Krum, Bulyan, median and trimmed mean, norm
  clipping, adaptive clipping, ALIE), for the server-side DP (DP-FedAvg, RDP accounting) and for
  FedMIA.
* The campaigns are stated to be our own measurements, not reproductions of the papers; a section
  on their limits (few clients, rounds instead of gradient steps, one dataset) and how to extend a
  campaign.
* Corrected: the ALIE paper's attackers do not know the honest updates; they estimate them from
  the corrupted workers (12 of 51).

## [Version 0.10.0]

Since `v0.9.0` (2026-10-16): sessions that end before their last round — on a signal, a button or
stopping criteria —, and federated learning on data arriving in lots — rounds at fixed times,
sessions launched again at each deadline —; the server's `check` refuses reports written twice.

### Ending a session before its last round

* A server stops after its current round on `SIGUSR1` (`kill -USR1 <pid>`), its reports written
  as at a normal end (final checkpoint, ONNX export): the first step of sessions not bound to a
  fixed number of rounds. Without the signal, a session runs its `num_rounds` as before.
* Stopping criteria (`server_run.stopping`): a session ends before its `num_rounds`, which stays
  its maximum, when a metric reaches a value (`threshold`), stops improving (`patience`) or the
  rounds have lasted long enough (`maxduration`); a new plugin category, `stoppingcriterion`.
* Session manager: a *⏹ stop after round* button does it from the page; the round counter shows
  `k/N ⏹` and the reason of the stop, the server agent ends *stopped*.
* Hierarchical sessions: when the top level ends before its last round (criterion, button,
  `SIGUSR1`), its lower levels end after the same round, their reports written, instead of waiting
  for a model up to their link's timeout; only the top level may end early (a lower level refuses
  `stopping`, its manager the button).

### Data arriving in lots

* Data arriving between rounds, the base of rounds at fixed times: with
  `client_run.refresh_data` a client reads its data again before each round; the `hdfs` plugin
  reads lots (`train.directory`, a file each) and with `train.lots: new` only those not trained on
  yet, remembered per client across sessions. A client with nothing to train on leaves the round
  instead of failing it; `--weights-path latest` starts a session from the last one's final
  weights; `pybiscus schedule preview` shows the deadlines of a period or of a cron expression
  ([configuration.md](docs/configuration.md#data-arriving-between-rounds)). New dependency:
  `cronsim`.
* Rounds at fixed times (`server_run.schedule`): every period (`every: 1h`) or at cron times
  (`cron: "0 2 * * *"`, with a time zone), the server waiting between two rounds; a round in which
  no client had new data is skipped and does not count among `num_rounds`; `maxduration` is also
  tested while waiting, and the stop button or `SIGUSR1` ends a wait at once; the manager's
  counter shows the rounds counted ([configuration.md](docs/configuration.md#rounds-at-fixed-times)).
* Repeated sessions: the `repeat` block of the session form (`every` or `cron`) has the manager
  launch the session again at each deadline once all its runs have ended, each one starting from
  the previous one's final weights (`server_run.weights_path: latest`, now settable in the
  configuration) and ending at once when no client has new data
  (`server_run.stop_without_new_data`); *🔁 stop repeating* launches no further session, a failed
  run stops the repetition ([sessionmanager.md](docs/sessionmanager.md#repeated-sessions)).

### Reports

* Reports written twice: the server's `check` refuses a configuration where two writers (the
  server, a metrics logger, a decorator) would write the same file of the reporting directory, or
  one in a directory another owns. A plugin used twice in the pipeline, to save before and after a
  transformation, takes a `tag`, the subdirectory of its files ([configuration.md](docs/configuration.md#files-of-the-reporting-directory)).
* FedMIA's default `.npz` files are prefixed with `fedmia_`, no longer those of the save decorators.

### Fixes

* A server whose session raises an exception (a plugin's defect) now ends, its clients
  disconnected: its process and its clients used to wait for ever.
* `FileMetricsLogger`: a path given as a string no longer fails, and a second instance no longer
  writes every line twice.
* Session manager: a boolean value set by the manager in a form (`true`) no longer stops the page
  from setting the values and locks after it.
* `visualizemodellayers` no longer fails a round in which no client trained.
* The clients' configurations given in `server_run.client_configs` are saved in the reporting
  directory again, not at the root of the file system.
* Agent forms: the input of a locked optional value (`weights_path`) is greyed like the other
  locked inputs.
* Flower's deprecation warning of `start_server()` and `start_client()`, at every launch, is no
  longer shown: Pybiscus runs on Flower's legacy API on purpose; any other Flower warning still is.

## [Version 0.9.0]

Since `v0.8.0` (2026-10-05): hierarchical federated learning — sessions federating other sessions,
on one machine or over the network — under development; the session manager shows a session's
network and keeps several pages consistent; the bundled plugins get a generated reference, and the
documentation's screenshots and videos a recording tool.

### Breaking changes

* **Plugin manifests**: the bundled plugins' manifest moves from the repository root
  (`pybiscus-plugins-conf.yml`) to `pybiscus-plugins/plugins-conf.yml`, each plugin directory
  carrying its own (paths relative to it). A `PYBISCUS_PLUGIN_CONF_PATH` naming the former file
  must be updated; without the variable, a file left at the former place is still read, with a
  warning, when the new one is missing.
* The relay client and the link decorator of the hierarchical sessions are in
  `pybiscus-plugins-hierarchical/`, with its own manifest, added only for those sessions: they do not
  appear in a simple session's forms.
* The FedMIA privacy evaluation decorator and its analyser, the iSAID data and FasterRCNN model
  plugins (PR #44, not finalized) move to `pybiscus-plugins-privacy-evaluation/`, with its own
  manifest, added only for the sessions that use them (the cifar10 privacy evaluation demo, the
  FedMIA campaign).
* **Bouquets**: a session manager started with `--bouquet` refuses (HTTP 409) an agent declaring
  another bouquet, most likely given the wrong manager's URL; `--bouquet-mismatch warn` registers it
  with a warning. An agent's registration form takes the manager's bouquet and locks it; an agent
  without a bouquet of its own (its default is now empty, it was `noname-bouquet`) gets the manager's.
* The manager's feeds (`/pybiscus-session/agents_logs`, `/logs`, `/metrics`, `/vignettes`) no longer
  empty on reading: they answer `{"items": [...], "next": n}` from `?since=<cursor>`.
* The mnist data plugin loads its batches in the main process by default (`num_workers: 0`, it was
  2): faster on a CPU-only session (5.7 s a round instead of 11.0 s on the demo).

### Hierarchical sessions (under development)

* **Managers linked into a tree**: a lower-level session manager (`--upper-url`, script
  `launch/session/run_lower_level_manager.sh`) reports its bouquet, agents and session to its
  parent; `--bouquet` and `--color` name and colour a session. The upper level's page shows the
  tree of the bouquets, the lower levels' agents and managers on its map, and their agents' states.
* **Configured from the top**: a lower-level session waits for its upper level's, whose model, its
  hyperparameters, data and number of rounds it receives locked; its own data partition, holdout
  and robustness stay its own.
* **Relays**: the upper-level manager designates, for each lower level, one of its clients as its
  relay (a client that trains nothing and loads no data), and refuses to launch without them.
* **The link between two levels**, set by the managers at each launch (a new `link_id`): the relay
  hands the upper model to the lower level's server and returns its aggregate, weighted by its
  examples; the lower server's `upperlevellink` decorator (added last to its pipeline by
  `server_strategy.upper_level_link`) takes that model at each round and publishes its aggregate.
  Two transports: a directory the relay and the server share on one machine, or the upper
  manager's **mailbox, over HTTP** (each end talking to its own manager with its own session's
  token, the lower manager relaying upwards), the two ends on any machines. The upper manager
  chooses each link's transport in its page, else `--link-transport`, else
  `$PYBISCUS_LINK_TRANSPORT`, else `directory`.
* Dropping a session stops its runs and its lower levels' sessions.
* The manager's page: cycles per level (where each level spends the rounds), constraints checked
  per level, a missing relay shown as a warning, map labels placed where they overlap nothing.
* **Network view** (`/pybiscus-session/network`, the 🌐 button): the machines, the processes
  listening on them (managers, agents, Flower servers), the flows from the one opening the
  connection to the one listening, the flows between machines a firewall must let through (CSV),
  and a shared-directory link across two machines flagged; the whole session at the head manager.
  `--machine` names a manager's machine in it.
* Several sessions side by side: `manager_url` in the server and client configurations (the
  webhooks' address, set and locked by the manager), nothing shared between agents started from one
  directory, a Flower server refusing a port already listened to (exit code 69) and a Flower port
  proposed per manager.
* `docs/hierarchical-session.md`: two experiments, a core and two edges, then a tree of four sessions
  on three levels, with their deployment, walkthrough and results.

### Session manager and forms

* Every page of a session reads the manager's logs, metrics and vignettes from its own cursor: two
  pages (two people, a person and the recording tool) show the same curves, and a page reloaded
  during a session finds its history.
* The loss panel says when no client evaluated the model (a session whose clients are all relays).
* `/pybiscus-session/identity` gives the session's bouquet, colour and location.
* Forms: the lock of an enum shown, a locked checkbox no longer clickable.
* Fit metrics: a first client without metrics no longer makes their aggregation fail (KeyError), and
  `visualizemodellayers` no longer empties the aggregated metrics of the decorators around it.

### Data and runs

* DataLoader workers are started by forkserver: forked from a process running Flower's gRPC
  threads, they aborted.

### Documentation and tools

* `docs/plugins-reference.md`: every bundled plugin, its fields, defaults and descriptions and the
  shipped configurations using it, generated by `pybiscus plugins doc` from the plugins' docstrings
  and field descriptions; `launch/ci/smoke.sh check` fails when it is not up to date.
* `launch/doc/record_session.py` and its scenarios (`docs/recording.md`): a session is shot (every
  page of it, with its events) then edited into a directed video or screenshots, again with another
  cut without running it again; it plays a simple or a hierarchical session, or follows one run by
  hand (`--attach`). The hierarchical walkthroughs' screenshots are shot by it.
* Agents and launch scripts of the `cortaixlabs-core` (5000–5008) and `cortaixlabs-edge1`
  (5100–5108) bouquets; the agent launch scripts have their shebang on the first line.

### Known limits

* The hierarchical sessions were run on one machine only: the link over the network and the
  network view were not tried on several. The mailbox keeps the objects in the upper manager's
  memory until read (1.6 MB a model for the MNIST CNN).
* The lower levels do not receive the model's hyperparameters given as a dict or a list; a relay's
  configuration still asks for a data section.
* iSAID and FasterRCNN were not run on real data; FedMIA is under development.

## [Version 0.8.0]

Since `dem_bx_0326` (2026-03-20): Pybiscus' functional scope grows — every
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
* The container images are tagged with the project's version (`pybiscus:0.8.0`,
  `pybiscus-agent:0.8.0`; they were `uv-v0.2`).
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
