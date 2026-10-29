# Changelog

## Unreleased

### Plugins

* `pybiscus plugins lint` checks two more rules (errors): `interface`, each class a plugin registers
  implements the interface of its category (a model a `LightningModule`, a strategy a
  `FabricStrategyFactory`...); `model-signature`, a model exposes `signature` (or
  `signatures(mode)`), a `TypedDict` with a `loss` key, read from the source (a module-level name or
  an attribute of `self` assigned one). No bundled or hierarchical plugin breaks them.
* A class that is not its category's interface is no longer dropped silently by the loader: a
  warning names it, whatever `PYBISCUS_PLUGINS_VERBOSE`, and its configuration is dropped too, so
  that `check` refuses a configuration naming it and gives the cause (it passed the check and failed
  at launch on a `KeyError` of the registry).
* The interface of each category is written once (`pybiscus/plugin/families.py`), read by the
  registries and the linter.
* The linter's regression check (`smoke.sh check`): probe plugins in `launch/ci/lint-probes/`, one
  or more broken rules each, marked `# expect: <rule>` on the line of the finding;
  `launch/ci/lint_probes_check.py` requires exactly those findings (15 today), a probe for each of
  the 13 rules, and the `check` refusal of a class not of its category's interface.

## [Version 0.17.0]

Since `version0.16.0` (2026-10-28): forms that know their bounds, relays without data, and the
recording tool on its own. The agents' forms show the bounds of the numbers and outline a value out
of them as it is typed, for every plugin; the core's types made precise (seeds, `devices`, SSL
paths, `opset`, ports). A hierarchical session's relay needs no data section. The client
watermarking fixed and its traitor tracing working. A Kubernetes example (k3s) in the CLI mode; an
agent in a container finds the repository's data. The shooting and editing tool becomes Näkymä
(`nakyma/`), a project of its own with its command, its README and an example.

### Recording

* The shooting and editing package `launch/doc/rushes/` becomes **Näkymä**, a project of its own at
  the repository's root (`nakyma/`: `pyproject.toml`, `src/nakyma/`, `README.md`, `examples/`), a
  first step towards a repository of its own; it still imports nothing of Pybiscus. The scripts
  using it (`launch/doc/record_session.py`, `launch/doc/demos/editor_demo.py`) declare it in their
  PEP 723 header as a local editable source; their commands are unchanged (the same video, byte for
  byte), and so is `session_manager --record`.
* The `nakyma` command (`nakyma edit <rushes> <cut>`, `nakyma ui <rushes> <cut>`, or
  `python -m nakyma`): the editing and the interactive editor without `record_session.py`, whose
  `edit` now calls them. A cut is read by the same YAML reader as the editor's (`ruamel.yaml`): the
  bundled cuts read the same.
* `nakyma/README.md`: the cut, the interactive editor, the rushes and how to write a driver, moved
  from `docs/recording.md`, which keeps Pybiscus' scenarios, views and events.
  `nakyma/examples/todo/`: a task list shared by two pages, its driver and its cut, the example of
  a driver for another application.
* The editor's write header is `X-Nakyma-Editor` (it was `X-Rushes-Editor`); missing caption fonts
  (DejaVu, Liberation) are reported once instead of falling back silently.

### Configuration

* The forms show the bounds of the numbers (`Field(ge=…, le=…)`, `PositiveInt`) ahead of their
  description (`≥ 1`, `0 … 1`) and outline in red a value out of them, or a text not matching its
  `pattern`, as it is typed: the bounds were only known to the check. A float takes any number of
  decimals (a step of 0.001 marked a learning rate of 1e-4 invalid). A constrained scalar
  (`Annotated[int, Field(ge=1)]`) is rendered as a scalar, not a union of one type. For every
  plugin, without any change to it.
* The server's `ssl` section requires its three paths (they defaulted to None, which the check let
  through: an incomplete section stopped the server only at launch); an ONNX axis requires its
  name.
* Seeds are integers from 0 to 2³²−1 (`server_run.seed`, `client_run.seed`, the data's seeds,
  the session's): NumPy refused a negative one at launch, Lightning replaced a larger one with a
  random seed. `opset` is 18 or more, as its description said (`configs/watermarking_5_clients/
  config_server1.yml` had 13, refused by the exporter); `client_run.cid` 0 or more.
* `hardware.devices` is an integer, 1 or more, or `auto`, or GPU ids (`0,1`): any text passed the
  check, a typo reaching Fabric only at launch.
* The session form's `server_port` is a port, 1 to 65535.
* An Optional section's style no longer reaches the unions nested in its value: a client's data
  (an Optional since the relays need none) showed its plugins' tabs out of place, and its last
  plugin (HDFS) could not be chosen, the rule hiding the Optional's None tab hiding it too. A
  value without a label (an Optional's) keeps its bounds under it.
* `docs/agent.md`, `docs/plugins.md`, `docs/configuration.md`, `docs/multi-machine.md`; the forms'
  screenshots taken again (`session_*` and `hier_*` of `docs/images`).
* `launch/doc/session_shots.py` takes the `session_*` screenshots of the forms from a real session
  (`docs/recording.md`).

### Docs

* The network view's screenshots taken again (`docs/images/network_machines.png`,
  `network_session.png`): they still showed the flows from the manager to the agents removed on
  2026-10-26 (ping, launch and stop of a run), so firewall openings no longer needed; 16 flows on
  four machines instead of 23, each client site with outgoing flows only.

### Hierarchical sessions

* A relay no longer needs a data section: a client's `data` is now optional for a client that
  trains nothing (`NEEDS_DATA = False`, the relay), left out or `null`; required otherwise, with
  a clear message (`data is required: only a client that trains nothing…`). The form still opens
  with a data section (an Optional without a default); the manager's presets unset it on a
  relay and lock it, as they set its relay plugin, so the relay's form no longer carries the
  session's dataset. `pybiscus/session/agent/presets.py` follows the form: an Optional without a
  default starts set, and an Optional around the plugins' union (`Optional[Annotated[Union]]`) is
  unfolded. `launch/ci/presets_cases.json` (`hierarchical-relay`: data unset, expected `null`);
  `docs/configuration.md`, `docs/hierarchical-session.md`.
* The forms' side menu no longer copies an Optional section's unset | set switch (the client's
  data, the first such section): its copy showed no state and acted on no section; the switch
  stays in the section. `docs/images/hier_relay_form.png` taken again.
* `pybiscus plugins lint` warns of a model's hyperparameter that is not a plain value (a list, a
  dict, a section; rule `model-hyperparameters`): a session sets and locks only plain values in
  every form and every lower level, the others being left to each. No bundled model has one.
  `docs/plugins.md`, `docs/hierarchical-session.md`.

### Plugins

* The client watermarking (`client watermarking` result modifier, in `personalizeclientsfitin`)
  fixed: it watermarks the global weights it is given (it marked the server's model as it stood,
  the global weights only when the server had evaluated them); its early stop reads the client's
  own fingerprint (it read the fingerprint of the iteration's number, stopping at the wrong
  moment); the match between Flower clients and fingerprints is written to
  `client_fingerprints.csv` (new field `client_fingerprints_path`) and each client's fingerprint
  saved when it first comes, whatever the round (before: round 1 only, the match in the logs
  only), so that a leaked model can be traced back; `traitor_tracing(weight, secret_key,
  fingerprints)` gives the fingerprint best read in a model (it could not run). On synthetic HDFS
  data, 5 clients: each reads its own fingerprint at a WSR of 0.98 to 1.0, the others' near 0.5,
  and the 5 clients' models are traced back to them. `configs/watermarking_5_clients/clients.sh`
  pointed at a directory that no longer exists.

### Containers

* A Kubernetes example, in the CLI mode: `launch/k8s/mnist_cnn/run.sh` runs the mnist demo
  (`configs/mnist_cnn/distributed/`) in a cluster, the Flower server and two clients as Jobs, the
  server behind the Service `flower-server:3333`, the configurations in a ConfigMap, the
  repository's `datasets/` and `experiments/` mounted (`hostPath`, one node), the reports given
  back to the user; a NetworkPolicy lets only the clients' pods reach the server's port, the Flower
  server not authenticating its clients outside a session; `stop.sh` removes the namespace. Tested
  on k3s (one node, CPU). `docs/containers.md` (In a Kubernetes cluster), `docs/usage-scenarios.md`,
  `docs/security.md`.
* `launch/agent/container/500{0,1,2}.sh` mount the repository's `datasets/` and `experiments/`
  (created if missing, podman refusing a missing directory): the runs an agent in a container
  launched found no data, and their reports went with the container.
  Each also mounts its own cache, `.pybiscus-cache/container-agent-<port>/` (inside, every agent
  listens on 5000 and the cache names its files by that port): its token and settings survive the
  container, its registration link stays valid.

## [Version 0.16.0]

Since `version0.15.0` (2026-10-26): plugins that describe and check themselves, lighter images. Each
plugin declares its dependencies (`requirements.txt`, `pybiscus plugins deps`) and is checked
against the conventions (`pybiscus plugins lint`); `get_modules_and_configs()` in `(class, config)`
pairs; `pybiscus plugins new` creates a plugin that runs as it is; an image with plugins of your
own; the images on Ubuntu 24.04 (13.9 GB → 6.3 GB), the GPU reached from podman as from docker;
Lightning without its extras, the privacy evaluation's dependencies in an extra.

### Plugins

* A plugin without `PYBISCUS_ALIAS` is labelled by its `name` Literal everywhere: its tab and its
  legend in the agents' forms (before: its class name) as its choice in the session form, so a
  preset of the manager selecting it selects its tab (before: the form kept its first option);
  `pybiscus/pydantic2xxx/pydantic2html.py` `option_label`, shared. `launch/ci/smoke.sh presets`
  loads a test plugin without alias (`launch/ci/test-plugins/`) and checks the configuration a case
  must give (`expect`).

### Dependencies

* Lightning without its `pytorch-extra` extra: of it Pybiscus and its plugins import only
  `omegaconf` and `rich`, now declared; `bitsandbytes`, `hydra-core`, `jsonargparse`,
  `tensorboardX` and `jsonnet` no longer installed. `scikit-learn` and `jsonargparse` in the extra
  `privacy-evaluation`, for the FedMIA analyser only (`uv run --extra privacy-evaluation …`,
  `docs/privacy-evaluation.md`); `pydeps` in the `dev` group; `dotenv` replaced by the package it
  redirects to, `python-dotenv`. The environment: 5.64 GB → 5.28 GB, 14 packages fewer.
* Each plugin declares its dependencies in a `requirements.txt` of its package: every third-party
  package it imports. `pybiscus plugins deps` checks the plugins of the manifest(s) without
  importing them: each requirement installed and satisfied (extras included), each import covered
  by the file; `--install` installs what is missing (when an extra of Pybiscus provides it, the
  command names the extra instead, for the locked versions), `--declarations` checks the files
  only. `launch/ci/smoke.sh check` runs it; `docs/plugins.md`, *A plugin's dependencies*.
* The container images install every extra (`uv sync --frozen --all-extras --no-dev`): they carry
  every plugin directory, the FedMIA analyser included; their build runs `pybiscus plugins deps`
  on all of them. `pydeps` no longer in the images.
* `get_modules_and_configs()` returns `(class, config)` pairs, each class registered under its
  config's `name` `Literal`: the name is written once (before: a registry key repeating it, refused
  when it differed). The former `(registry, configs)` is still accepted. The 44 plugins and core
  modules migrated, their registries unchanged (same keys, classes and order of the configs); a
  config without a `name` `Literal`, not a `BaseModel` or under a name taken twice is refused
  with its cause. `docs/how-to.md`'s templates; the examples of `docs/pybiscus_model_guide.md`,
  which returned `(config, class)`, a form the loader never took, corrected.
* `pybiscus plugins new model|data|strategydecorator <name> [--dir <plugin directory>]` creates a
  plugin that runs as it is: its package (configuration with its descriptions, implementation,
  `get_modules_and_configs()` in pairs, `requirements.txt`), its entry in the directory's
  `plugins-conf.yml` (created if absent, comments kept) and `examples/`, a server and two clients
  using it on synthetic data. The name is refused when it is not a lowercase identifier, is
  already a module (it would shadow the plugin) or a plugin of the family. `launch/ci/smoke.sh
  new` creates one of each family and runs their examples; `docs/how-to.md`, *The quickest way*.
* `pybiscus plugins lint` (`pybiscus/plugin/pluginlint.py`, `docs/plugins.md`, *A plugin's
  conventions*): each plugin of the manifest(s) against the conventions the forms and the sessions
  rely on: it imports, the manifest lists every plugin package beside its modules, no `print`,
  `extra="forbid"` and a description on each field of the configuration models it defines, a
  `PYBISCUS_ALIAS` (warning only), a `PYBISCUS_GROUP` for a strategy or a strategy decorator, a
  strategy built on `FlowerStrategyFactory` whose `aggregate_fit` calls Flower's, a data
  configuration in `train` / `val` / `test` sections, `ReportingOutputs` for a plugin reading the
  reporting directory; exit 1 on an error, `# pybiscus-lint: ignore=<rule>` for a justified
  exception, `--rules`. `launch/ci/smoke.sh check` runs it on the bundled and the hierarchical
  plugins, `smoke.sh new` on the plugins `plugins new` creates; the privacy evaluation's are left
  out until finalized. The bundled plugins needed two fixes: the `print` of the `randomvector` and
  `vector` examples, and the test plugin `omniscientalie`, unlisted on purpose.
* An image with plugins of your own: `container/build_container_with_plugins.sh <plugin directory>
  [image]` builds on the Pybiscus image (or the agent's, `PYBISCUS_IMAGE`), installs each plugin's
  `requirements.txt`, adds its manifest to `PYBISCUS_PLUGIN_CONF_PATH` and runs
  `pybiscus plugins deps` at build (`container/Dockerfile_with_plugins`; `docs/plugins.md`,
  *Plugins in a container*).
* The container images on Ubuntu 24.04 instead of `nvidia/cuda:11.7.1-cudnn8-devel-ubuntu20.04`:
  13.9 GB → 6.3 GB. torch's wheels carry their own CUDA (13.0), which the base image's 11.7 and its
  compilers duplicated unused; the GPU is still reached through the host's driver (NVIDIA Container
  Toolkit), `NVIDIA_VISIBLE_DEVICES` / `NVIDIA_DRIVER_CAPABILITIES` kept. `bin/container_gpu`: the
  launch scripts' GPU option for docker or podman (`PYBISCUS_GPU`: a device, `all`, `none`); they
  passed `--gpus device=0`, which podman cannot read. `SMOKE_GPU=1 launch/ci/smoke.sh
  container-run`: the session in containers on the GPU; `docs/containers.md`, *The GPU in a
  container* (WSL2 included).
* The test-only plugins (`byzantine`, `omniscientalie`) have their `requirements.txt`, and
  `smoke.sh check` checks the declarations of the campaigns' and the presets' test manifests.

## [Version 0.15.0]

Since `version0.14.0` (2026-10-20): sessions over several machines secured. HTTPS between the
manager and the agents, invitations of the sites and of the agents, a production web server; the
manager calls no agent any more, the agents ask it for their orders, may register and launch their
runs without a browser; the Flower clients of a session authenticated by its Flower server; the
usage scenarios and `docs/security.md`; Flower 1.42.0.

### Session

* **Invitations** between the managers of a hierarchical session (`docs/sessionmanager.md`,
  *Invitations*): the upper level invites each site (`session_manager invite --bouquet <site>`, or
  its 📨 *sites* page), with a token of its own, bound to its bouquet, valid 90 days by default and
  revocable (`session_manager revoke`); the site's manager starts with `--invitation <file>` in place
  of `--bouquet`, `--upper-url` and `--upper-token`, and trusts the CA the invitation carries. The
  token opens only the routes of a lower level (its reports, the mailbox of its own link); a bouquet
  invited cannot be reported under with the session token; an invited site's link goes through the
  upper manager's mailbox, its relay at the upper site. `--require-invitation` (or
  `PYBISCUS_REQUIRE_INVITATION=1`) refuses the lower levels without an invitation. The sites page
  lists the sites invited, present, gone silent, expired, revoked and refused. Invitations only for
  a manager in HTTPS. `invitations/` (not committed): `issued/<upper>_downto_<site>.yml`,
  `received/`, used by `launch/session/run_*manager.sh`. `record_session.py`: `invitations: true`
  in a hierarchical scenario (HTTPS).
* **Agents' invitations** (`docs/sessionmanager.md`, *Agents' invitations*): the manager invites
  each agent (`session_manager invite --agent <name> --role client|server`, or its 🎫 *participants*
  page), with a token of its own in place of the session token, bound to its name and role, valid
  90 days by default and revocable (`session_manager revoke --agent`); the agent starts with
  `pybiscus_agent --invitation <file>` next to its `--config`, the invitation prevailing over the
  configuration (manager URL, name, role, token; a contradiction warned about) and locking them in
  the registration page; its runs present the token for their webhooks. An invited name is never
  registered with the session token; an invitation's token acts as its own agent only (registration,
  session parameters, states, the mailbox of the link a relay relays). `--require-agent-invitation`
  (or `PYBISCUS_REQUIRE_AGENT_INVITATION=1`) refuses the agents without one. The participants page
  lists the agents invited, registered, expired, revoked, registered with the session token and
  refused. `launch/agent/cli/<port>.sh` look in `invitations/received/` for the agent's own
  (`launch/agent/received_agent_invitation.sh`); the managers' scripts take only the
  `*_downto_*` files there. `record_session.py`: `agent_invitations: true | required` in a simple
  scenario (HTTPS).
* **The agents ask the manager for orders**: the manager never calls an agent any more. Each agent
  asks the manager every second during a session, every 5 s otherwise
  (`GET /pybiscus-session/orders`), executes the orders queued for it (stop, stop after the round,
  relaunch of a repeated session, whether its server listens) and posts their results; an agent
  unheard of for 15 s is shown as no longer heard from. A client's run configuration goes to the
  server's agent through the manager (`POST /pybiscus-session/runconfig`), no longer from agent to
  agent. A client agent may thus sit behind a NAT, or listen on its loopback when its operator's
  browser runs on its machine; the server agent is still opened by the browser of the manager's
  operator (the session form), the Flower server by the Flower clients. The agent's routes `/run/relaunch`, `/run/listening`,
  `/run/stop-after-round` and the server's `/session/log/client/<name>/runconfig` are gone.
* Each agent gives the manager a **call token** at its registration, which it presents when it asks
  for its orders (`X-Pybiscus-Call-Token`) and when it sends a client's run configuration: with the
  session token alone, any participant could take another one's orders or post a configuration in
  its name. The manager presents it to open the server agent's session form.
* The listening probe, which the manager asks before it launches the clients of a repeated session
  again, checks only the port of the agent's server run (read from its configuration): any port
  asked for would tell which services listen on the loopback of its machine.
* **Launch by order** (`docs/sessionmanager.md`, *Launched by order*): an agent started with
  `pybiscus_agent --accept-launch` (or `PYBISCUS_ACCEPT_LAUNCH=1`) needs neither its form nor an open
  tab at the launch. When the session is launched, the manager orders it to launch its run: the agent
  asks the session's presets, applies them to `--launch-config <file>` (its own data paths, devices...;
  default: the form's defaults) as the form would, checks the result and starts the run. The servers
  first, the clients once every server listens (even one its operator launches from its form); an
  agent registered after the launch is launched at its registration; a failure is in the manager's
  log. A session may mix both. The registration still goes through the agent's page, whose waiting
  page follows the run's monitor; the manager's page marks such an agent *🚀 by order*. The form's
  default list items (loggers, metrics loggers, pipeline) come from `presets.LIST_DEFAULTS`, shared
  with the launch. `record_session.py`: `accept_launch: true` (scenario or agent) and an agent's
  `launch_config`.
* **Registration without a browser** (`docs/sessionmanager.md`, *Register the agents*): an agent
  started with `pybiscus_agent --register` (or `PYBISCUS_REGISTER=1`) registers itself at its start
  from its `--config` registration file and its `--invitation`, as its page would (the manager's
  bouquet when the file names none, its place, machine, call token, `--accept-launch`); it registers
  again every 5 s while the manager does not answer, a refusal logged and not retried. With
  `--accept-launch`, an agent takes part in a session without any of its pages. The page and
  `--register` share `pybiscus/session/agent/registration.py`. `record_session.py`: `register: true`
  (scenario or agent) starts the agents with `--register`.
* `launch/ci/smoke.sh session` (`launch/ci/session_check.py`): the smoke run in a session of the
  manager, without a browser: three agents started with `--register --accept-launch` before their
  manager register by themselves (the smoke run's configurations as `--launch-config`), a
  registration under a name taken is refused without touching the registered agent, the session is
  launched through the manager's API, the three runs launched by order succeed (round reached, final
  checkpoint, no traceback).
* **Flower clients authenticated in a session** (`docs/security.md`, *Flower clients*): the Flower
  server of a session accepts only the session's clients, one connection each. The manager draws a
  key at each session launch (kept by its repetitions); a client's token is the HMAC of its agent's
  name under it. Each agent asks for its credential before its run (`GET
  /pybiscus-session/flower-credential`, with its call token: a client its token, the server the key)
  and passes it to the run through the environment, never in a YAML file. The client presents it in
  its gRPC metadata; a client without one, with another's or under a name already connected is
  refused (`UNAUTHENTICATED`) and stops. Flower's legacy API takes no credential:
  `pybiscus/flower/clientauth.py` gives its gRPC server an interceptor and wraps the client's
  channel. Outside a session (CLI), nothing changes. `smoke.sh session` launches two intruders.
* Fix: the flows of a session left over from before the agents asked for their orders: the network
  view (and its CSV for the firewalls) no longer lists a flow from the manager to each agent, and
  `docs/security.md` (*Across sites*) no longer lists the client agent to the server agent nor the
  manager to the client agents; no flow enters a client site.
* Fix: a refused registration (a name registered under another URL) no longer replaces the
  registered agent's metadata in the manager (its URL, place, whether it is launched by order): its
  run was no longer launched by order.
* `pybiscus/session/agent/presets.py`: the session's presets (options and values the manager imposes)
  applied to a configuration in Python, as the agent's form applies them in the browser, for an agent
  launched without its form; the form and the Python merge share the filter of the values calling an
  interpolation resolver. `launch/ci/smoke.sh presets` (`launch/ci/presets_check.py`) checks that both
  give the same configuration, on the presets of a session, of a hierarchical one and synthetic cases.
* `record_session.py`: scenario keys `repeat` and `sessions`, `stop_after_round`,
  `drop_after_round` (`docs/recording.md`).
* `docs/security.md`: what the manager and the agents protect, code and data, the defences against
  the participants, the known limits and a checklist by scenario; linked from the usage scenarios,
  the docs index, `multi-machine.md` and `sessionmanager.md`.
* `docs/usage-scenarios.md`: a deployment diagram for the scenarios that differ (one machine,
  automated runs, closed network, several organisations, tunnel or proxy), and a link from each
  scenario to its checklist in `docs/security.md`, which links back.
* `docs/usage-scenarios.md`: containers and orchestrators (Kubernetes) in the closed-network
  scenario: the CLI suits a cluster, a session of the manager less so; no manifest provided yet.
* `docs/security.md`, *Across sites*: the flows a VPN between the sites lets through, for one
  session over several sites and for a hierarchical one (one flow, lower manager to upper manager,
  with the `manager` link transport and the relays at the upper site).
* `docs/multi-machine.md`: one agent per machine, with the machine's role (two on a machine that
  both aggregates and holds data), the manager on the server's machine or on its own.
* The server loads its initial weights (`server_run.weights_path`) as tensors only
  (`weights_only=True`): for a path starting with `http`, Lightning unpickled the file whole.
* `certificates/`: no default password for the CA's key any more (`set_env.sh` held `12345678`):
  `gen_from_env.sh` asks for it twice, `sign_component_csr.sh` once, or both read it from
  `rootCApass`; openssl gets it from the environment, not from its command line. A signature with
  a wrong password no longer leaves an empty certificate.
* The manager's page takes a session form's values only from the frame of its ⚙ *Config* button, at
  the server agent's origin, and answers it at that origin only: a page of another site that framed
  or opened the manager's page could launch a session with its own values. The session form posts
  them to the manager's origin only. The manager's pages may be framed by their own origin only, an
  agent's by its own and by the manager it registered with (`frame-ancestors`).
* The URL an agent registers or starts with must be `http://` or `https://`: it ends in the
  manager's page, as a link and as the session form's frame.
* The requests to the manager and the agents are bounded at 16 MiB, a model put in the manager's
  mailbox at 1 GiB. A vignette needs an integer column and row (a vignette without them failed).
* A value the manager sets in the agents' forms can no longer call an interpolation resolver
  (`${oc.env:NAME}`…), which would read the agent's machine: the session form refuses it under its
  field, an agent ignores it and says so under the field and in its log. References to other fields
  (`${root_dir}/…`) stay.
* A lower-level manager takes from its upper level only the model, its hyperparameters
  (`model.config.*`, without interpolation), the data plugin, the number of rounds and a valid link:
  any other field would have been set and locked in its agents' forms. What it ignores is named in
  its log and in the page.
* The values a manager presets in the agents' forms are written into the page as JSON: a value
  holding a quote broke the page, and a crafted link could run a script in the agent's page. The
  server form's GET no longer changes the agent's state.
* Without tokens (on the loopback), the manager and the agents answer only a request naming the
  loopback (`localhost`, `127.x`, `::1`): a site re-pointing its name to 127.0.0.1 (DNS rebinding)
  could otherwise drive them. A reverse proxy passing its own host name is refused too, with the
  advice to start the component with `--require-token`.
* HTTPS between the manager and the agents: `--tls-cert` / `--tls-key` serve HTTPS, `--tls-ca`
  trusts the session's CA, here and in the runs launched, besides the usual authorities. The
  printed and linked URLs, the access cookie (`Secure`) and the network view follow; a component
  listening beyond the loopback without TLS warns at start, the manager warns at the registration
  of a remote agent in HTTP (its page would be blocked inside the manager's), and an untrusted
  certificate is named in the logs. `docs/multi-machine.md` (Encryption).
* `certificates/`: one certificate per machine for the manager, its agents and the Flower server
  there (`gen_component_cert.sh`, or `gen_component_csr.sh` on the machine and
  `sign_component_csr.sh` at the CA: the key never leaves its machine); `gen_from_env.sh` refuses to
  replace an existing CA and no longer makes client certificates (unused by Flower).
* `launch/doc/record_session.py shoot --tls-cert --tls-key --tls-ca`: a scenario's managers and
  agents in HTTPS.
* Removed: the `/pybiscus-session/ping-server` route (unused, read an undefined attribute).
* The manager and the agents run on **cheroot**, a production WSGI server (a pool of 64 threads,
  a client that stops reading dropped after 30 s, TLS with `--tls-cert`), in place of Flask's
  development server; Ctrl+C still ends them at once, an open run monitor included. `--debug`
  (the agent's, and now the manager's) keeps Werkzeug's server for its reload on code change and its
  in-browser debugger; `docs/security.md`.

### Robust aggregation and privacy

* `clipping` decorator: `size_scaling: sqrt_examples` compares the update norms at the median share
  size. At 20 clients on dirichlet shares (`launch/campaign/cifar10_clipping_size_20clients.yml`,
  3 seeds), clipping x1.5 reject x1.7 rejected the largest honest client in 7 rounds of 10 and lost
  2.1 points to FedAvg; with the scaling it keeps it, matches FedAvg without attacker and still
  rejects 5 sign flippers x10 every round; `docs/robust-aggregation.md`. **On by default**: a
  configuration that relied on the former behavior sets `size_scaling: none` (the bundled
  campaigns measured before it do).

### Dependencies

* Flower 1.40.0 → 1.42.0 (`flwr>=1.42.0`): it requires `uv` ≥ 0.13.5 and `certifi` ≥ 2026.10.19
  after the eMudhra CA incident; no change in Pybiscus.
* Known vulnerabilities fixed: `pillow` 12.3.0 → 13.0.0 (35, in its TIFF, GIF, PDF, EPS, BMP and
  JPEG 2000 decoders), `certifi` 2026.2.25 → 2026.10.23 (PYSEC-2026-4320), `gitpython` 3.1.62 →
  3.2.1 (CVE-2026-114145, through wandb), `uv` 0.12.24 → 0.13.5 (PYSEC-2026-4321, through Flower);
  `pip-audit` finds none left in `uv.lock`.
* Added: `cheroot` 11.1 (the web server of the manager and of the agents; pure Python).
* Known vulnerabilities fixed: `filelock` 3.25.1 → 4.2.4 (CVE-2026-112940, CVE-2026-112913,
  CVE-2026-112907: its SQLite reader/writer locks and, on Windows, its soft locks; Pybiscus uses
  `FileLock` only), `setuptools` 83.0.0 → 84.2.1 (GHSA-xmj3-9gf7-h52w: its legacy wheel-to-egg
  installation, on Windows); `setuptools<84` becomes `setuptools>=84.1`, `filelock>=3.25`
  `filelock>=4.2.1`.

## [Version 0.14.0]

Since `version0.13.0` (2026-10-19): the manager tells what to do next, sums up an ended session and
fits its charts; sessions recorded from the manager (`--record`, the session form's box, a record
button) and an interactive editor for the recordings (`edit --ui`, mosaic, screenshots, export);
server-side differential privacy and FLTrust measured at 20 clients.

### Dependencies

* `pip-audit` finds no known vulnerability in `uv.lock`; no dependency changed.

### Robust aggregation and privacy

* Server-side differential privacy at 20 clients (`launch/campaign/cifar10_serverdp_20clients.yml`,
  3 seeds): at epsilon 20, a tight bound (C 0.5, most clients clipped) loses 7 points to FedAvg, a
  loose one (C 1) 15, the adaptive bound in between; `docs/configuration.md`.
* FLTrust at 20 clients, 5 attackers (`launch/campaign/cifar10_fltrust_20clients.yml`, 3 seeds):
  3.5 points lost without attacker, 5 sign flippers x10 stopped (FedAvg falls to chance), ALIE at
  z 1 let through like FedAvg; `docs/robust-aggregation.md`.

### Agent pages

* Config forms: readable labels for the adaptive strategies' parameters (Server learning rate (η),
  Client learning rate (η_l), Adaptivity (τ), First / Second moment decay (β₁, β₂)), FedProx's
  Proximal term weight (μ), ALIE's Deviation (z), the models' `mid_shape`, the client's Validation
  before training; `*_sub_dir` reads "subdirectory".
* Session form: a session the manager refuses keeps the form open, each problem in red under its
  field (`repeat.every`, `repeat.timezone`, `num_rounds`…) or under *Run session*; it used to close
  the form and show the message in a browser alert. The schedule's errors name their field
  (`pybiscus schedule preview` says which option).
* Check errors (agents' forms and session form): an error about an unset optional field (`num_rounds`
  required by lower levels) shows under its title, instead of under the buttons; the messages under
  the buttons, over the form, on an opaque background (the form showed through them).

* Manager charts (main metric, loss): the scale fits the values, on round steps (accuracies ending
  at 0.99 were one line along the top of a 0–1 scale, a loss of 0.03 flat at its bottom); *0–1*
  brings the whole scale back; the axis numbers the rounds (every 2, 5, 10… when they are many);
  the main metric's chart gets *r0* too, round 0 hidden by default (the untrained model's test
  stretched the scale down to 0.1).

* Manager: a summary under the top bar once the session has ended: finished or stopped (and why),
  rounds run, duration from round 1, last values of the main metric and of the loss, the server's
  reports directory with *copy* (it showed only in the server's log). The server logs its reports
  directory as a GUI event (`gui reporting_path=`), after its loggers are set (before, it reached
  its console only); the manager stamps the log lines it receives with their time.
* Manager: the topology's metric column wide enough for "accuracy" (fixed widths: in em, the
  header's smaller font made its columns narrower than the rows'); *Δ round* reads *round time*,
  its tooltip saying what the value and the bars are.

* Manager logs: each line with the time the manager received it (the date on hover); in the
  server's log, the reports directory reads `…/<its last directory>`, the whole path on hover (it
  wrapped the lines of the saved configs on three lines).

* Manager: the next step under the top bar until the session runs (register a server, then the
  clients; relays; *⚙ config* and *Run session*; *Check* then *Execute* on the server, then on the
  clients). The agents started with `--config` and not registered yet listed in the topology,
  dimmed, with *register ↗* to their registration page: the topology said "no agents yet" while
  the agents' log showed them started (an agent sends its URL and role with its start).

* Manager before the first round: the two charts a line each ("the curves start with the first
  round") and their column narrower, the topology taking the width (unless a column was dragged);
  the map says that the sites appear as the agents register (empty axes and an empty grid took most
  of the screen).
* Manager: *Drop session* asks first while the session runs (it stops the runs); once the session
  has ended it reads *⟲ new session*, no longer in red.
* Manager: the *diff* chart (change of the evaluation loss) placed by round, its last 40 rounds,
  with the fitted scale and the round numbers of the other charts (its values were placed in their
  order of arrival, without numbers, on three lines); the `metricdiffcompute` decorator logs its
  round (`gui metric_diff round= value=`). A started agent that no longer answers the manager is
  marked *not reachable* (it stayed listed as started).
* Manager: between two sessions of a repeated session, *Drop session* stays red and asks first (it
  read *⟲ new session* once each session ended, though it cancels the next ones).
* Documentation: the screenshots of the manager redone (`docs/images`).

### Recording

* The manager's page has a **⏺ record** button: it films from now on (before the registrations or
  during a session), *⏹ stop recording* ends that recording, edited and copied into the session's
  reports; with `--record`, the next sessions are recorded again. Disabled, with the reason, when the
  manager's machine cannot record.
* The session form's `record` box films that session only (a manager whose machine cannot record
  refuses it, the reason under the box); a recorded session's video is copied into the server's
  reports as `session-video.mp4` / `.webp` when they are on the manager's machine; the manager's
  page shows a **● REC** pill while the session is filmed, then where its video is.
* `session_manager --record [DIR]`: the manager films each of its sessions (its page, the agents'
  run monitors as tiles, captions from its events) into `DIR` (default `experiments/recordings`),
  with `launch/doc/record_session.py shoot --attach` run by `uv` in its own process: no new
  dependency. A recording starts with the manager, after a drop, or joins a session launched while
  none records; the manager's Ctrl+C ends it, its video edited all the same. `--attach` takes the
  manager's administration token from `$PYBISCUS_MANAGER_TOKEN` too.
* A view's panels: an element's id, a CSS selector, or a selector and the container to take
  (`(name, selector, "section")`); `launch/doc/rushes/` no longer assumes Pybiscus' `<section>`
  around a panel. `launch/doc/demos/editor_demo.py` shoots `edit --ui` at work with the same tool,
  edited by `launch/doc/demos/editor-demo.cut.yml` (a cursor drawn in the page).
* A cut's `overrides:` change one scene (the `index`-th of its kind): its start (`offset`), its
  `duration`, its main view, inset, caption or pace, its inset's `corner` and `width`, or leave it
  out (`skip`); a rule applied to every scene of its kind. The editing computes the plan of the video
  (its images, in order) apart from rendering it.
* `record_session.py edit <rushes> <cut> --ui`: a local page showing the rushes on a timeline (the
  scenes, the events, a track per view), the cut's image at any moment as the export composes it,
  the video played from its plan, the selected scene's settings; it follows the cut's file as it is
  edited, and shows a wrong cut's message.
* `edit --ui` changes a scene's settings, for that scene (an override) or for every scene of its kind
  (the rule), each change checked by computing the plan again, a scene left out or brought back;
  *Save* writes the cut with its comments (ruamel.yaml, the previous file in `.bak`), asking first
  when the file changed on disk; *Revert* drops the unsaved changes.
* `edit --ui` takes screenshots: the view shown (or one of its panels) at the moment shown, or a take,
  listed with their image, renamed, removed, marked on the timeline; a cut of screenshots only opens
  too. A shot of a cut takes `after: <seconds>` after its event.
* `edit --ui` exports the video and the screenshots of the saved cut, the same files as `edit`, with
  its progress, the files written and the video played in the page; the video's path and formats are
  set there.
* Mosaic: a scene's `tiles` (views, `*` matching several) show the main view smaller and beside it a
  tile per view, in their order of appearance, `highlight` outlining one (`"agent:{turn}"`); the
  tiles in a column on the right (default) or a row at the bottom (`mosaic: {side, slots}`, or per
  scene); set in `edit --ui` too. A cut without tiles gives the same video as before.
* `docs/recording.md` shows `edit --ui` (scenes in mosaic, screenshots, export) and the two layouts of
  the mosaic; the page plays the animated webp where the browser has no H.264.
* `shoot --attach` opens the run monitor of each agent launching its run (`--agent-pages`, 4 by
  default; `--agent-token` for an agent beyond the loopback); `attach.cut.yml` shows them as tiles
  beside the manager. A scene with tiles and no view to tile yet is composed as without tiles.

## [Version 0.13.0]

Since `version0.12.0` (2026-10-18): the GUI reworked — one dark theme (with a light one) shared by
the manager and the agents' pages; configuration forms with a section menu, readable labels,
descriptions shown, the check's errors under their fields, compact lists and the server's pipeline
drawn as chains; the run's progress on the agent, the session's state, metrics table and curves in
the manager —; ALIE measured at the paper's proportion of attackers; screenshots of the docs taken
again.

### Dependencies

* Known vulnerabilities fixed: `aiohttp` 3.14.3 → 3.14.5 (GHSA-2g87-pp6c-29x5, CVE-2026-111063,
  CVE-2026-111064; `yarl` 1.23.0 → 1.25.1 with it); `pip-audit` finds none left in `uv.lock`.

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
* Run monitor: the round (out of the session's rounds on a server, with a bar), its phase, the last
  main metric of each phase and the last round's duration; a view of the log by rounds, or by
  warnings and errors. New `gui_events` lines: `round_start` (server), `client_phase` and
  `client_metric` (client, kept out of the manager's charts). A run launched by the agent gets a
  200-column console: at 80, Rich cut those lines in two.
* Manager: the session's state in the top bar (waiting, ready, running, finished, stopped, failed…)
  in place of a "live" mark that went on blinking once the page had stopped reading; Drop session in
  red; the topology as a table of the agents (site, state in words and colour, the server's round
  and last test value).
* Manager metrics: a table, one row per client and one for the server's test, the loss and main
  metric of the last round for fit and evaluation (*all metrics* for the others), older values
  greyed, ▼ ▲ on the clients at the lowest and highest main metric (ties included, not for more than
  half of them), a *spread* row (max − min); *raw* keeps the former list. The clients are
  named from their cid: `/pybiscus-session/agents` returns the session's cids, a relay now returns
  its cid in its fit metrics (its rows showed Flower's id). The agents table shows a client's round
  and last evaluation value; a relay's "→ lower level" mark sits under its name, no longer cut.
* Manager vignettes: folded by default into a strip that counts the rounds received (many sessions
  have no `VisualizeModelLayers`, and the empty panel took a third of the width), the charts taking
  the width; *hide* / a click on the strip, the choice kept by the browser. Shown, the matrix follows
  the last round unless scrolled back, its layer and round labels stuck to its edges.
* Manager panels in windows of their own (several screens): the ⧉ of a panel opens it alone (the page
  with `?panel=<name>`), the main page giving its place to the others; its mark in the top bar, its
  window's *dock* button, or closing the window, brings it back; the actions stay in the main page;
  the detached panels and their windows' places kept by the browser, the main page offering to
  reopen them. The charts are drawn at their size on screen: their axis figures were stretched with
  the panel.
* Theme: the manager, its network page and the access-token page share one set of colour tokens
  (`pybiscus/session/theme`), dark by default, light with the 🌓 button of the top bar; the choice is
  kept by the browser for each manager and followed by its other open pages; `?theme=dark|light`
  forces it for one display without keeping it. The server's config page shown in the manager (an
  agent's page) receives the manager's theme.
* Theme: the agent's registration, waiting and run monitor pages on the same tokens, with their 🌓;
  the success, failure and stopped banners have their light version.
* Theme: the configuration forms on the same tokens; their 16 themes and the 🌞 / 🌙 / cycling 🌓
  buttons replaced by one 🌓 (dark by default, teal accent as on the other agent pages); the server's
  config shown in the manager follows the manager's theme (URL, then message on each switch). The metrics table missed its main metric column when
  the line naming it came after the first metrics.
* Manager charts: curves that coincide (evaluation = test, the clients validating on the official test
  set) drawn in dashes of their colours in turn, the last drawn hid the others; *clients* shows each
  client's main metric around the average of a phase (evaluate by default, or fit): a point per
  client and the min–max band; hovering the chart shows the nearest round, its averages and every
  client's value, sorted (a point hovered alone missed those under a curve, and of clients at the
  same value showed one at random). Past 12 clients, the points of the hovered round only and the quartiles'
  band (40 clients made a bar of points per round, hiding the averages); the tooltip lists the 5
  highest, the median and the 5 lowest (with 40 clients it outgrew the chart, clipped).
* Manager: the loss per round in the middle panel's *loss* tab, as the main metric: fit and evaluate
  averages, the server's test, each client's loss with *clients*; the former chart, the change of
  the evaluation loss, under *diff*; *cycles* and *constraints* shown in a hierarchical session
  only. The server logs the loss of each phase in a line of its own (`round_loss`). The loss of round 0
  (the untrained model's test, which flattened the later rounds) hidden by default, shown with *r0*;
  a logarithmic scale with *log*. A panel's header wraps when narrow (the loss panel's last buttons
  were cut off). Each value is placed by its round: the server's fit
  and evaluate averages now log theirs (`round=-` before), and past 40 rounds the training and
  evaluation curves were drawn one round off the test's.
* Config forms: an optional field's checkbox replaced by *unset | set*, unset showing the field's
  description (what None means); the checkbox stays, hidden, driven by the switch: YAML, presets,
  pins and locks unchanged.
* Config forms: a compact top bar that stays in view when scrolling: the form's name, the agent's
  name, role, site and bouquet when it is registered in a session, the config's origin and the
  buttons on one line (two when narrow); the check's messages show under Check without moving the
  bar. A scroll to a field (an error, the menu) stops under the bar.
* Config forms: the section menu in a column on the left, staying in view when scrolling (back on
  top when the window is narrow); the shown section titled by its name, with its description under
  it (it was only on hover).
* Config forms: flat blocks: a nested block (model, option, union, list item) drawn by a rule on its
  left in place of a framed box, the rule of the block under the pointer in teal (which block a field
  belongs to); a list on a sunk background; a block refused by the check with a red rule and title, a
  locked one with a dashed rule. The shown section has no frame. More width is left to the fields.
* Config forms: in a compact list (the chain of items), the shown item no longer repeats its rank
  above its values, the chain's current node showing it.
* Config forms: a list whose items hold a list of their own (a W&B logger's tags, among the metrics
  loggers): the item's template no longer carries a stray copy of the inner list before the item,
  shown with the rank while the item kept the template's `#` (the generator built the inner list in
  the outer one's context); ➕ on the outer list no longer clones the inner list's template (an
  unscoped search found it first), nor does the numbering read its paths; the ➕ of an inner list in
  an added item works (a cloned button had no listener).
* Config forms: a long list's chain scrolls within the form's width, its ←/→/➖/➕ staying in view;
  the chain widened the whole section past the window, the controls after it out of reach.
* Config forms: a compact list's ← ➖ → under the current item, which they act on, scrolling with it
  (at the end of the line they could be out of view); its ➕, the same as the ➕📝 next to the list's
  name, removed; a move that cannot be made is hidden instead of greyed.
* Config forms: the client form's lists (a dataset's engines...) work: their ➕📝 did nothing, the list
  script being loaded by the server form only (the session form loads it as well).
* Config forms: a compact list's removed item fades out before it goes (among identical items,
  removing one in the middle looked like removing the last one).
* Config forms: a union's options restyled: two options as a segmented control (one track, the
  chosen segment in teal, like *unset | set*), up to eight as a list like the section menu (a teal
  tint and bar), more as chips with the chosen one in teal (the others keep their family's colour);
  the white fill of the chosen option, the dimmed others and the sweeping sheen are gone. The
  options' names, which the presets and pins compare, are unchanged.
* Manager: the session number (`SESSION n`) shown only for a repeated session; it showed
  `SESSION 1` in every session.
* Config forms: the pipeline drawn from its strategy (a node that leads to it), with the decorators
  `robustness: safeguard` and `upper_level_link` add, dashed, where they run; the decorators' rules
  (incompatible, order, last, strategies) flagged as the pipeline is edited, with the check's
  messages, in both views of the list; "no settings" for a decorator without any (was "⚙️🈳 empty
  configuration"). The options carry their `name` and rules as attributes; a configuration class
  declares its chains with `PYBISCUS_CHAINS`.
* Config forms: descriptions shown: each field's under its value, each block's (model, union,
  option once set, list) under its title, an unset option's in full (it was cut at one line); they
  were on hover only. Widths by type: integers and floats narrow, paths, directories, files and URLs
  wide (from the field's name or its default value, which were cut off), fixed values at their
  text's width.
* Config forms: a locked field's value readable in the dark theme (the faintest grey, dimmed twice).
* Config forms: a locked field's lock back on its label's line (it took a third line under the key).
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
