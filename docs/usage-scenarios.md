# Usage scenarios

Pybiscus runs the same federated session on one laptop, on the machines of a lab, or across
several organisations. What it brings, what has to be set up and what its results mean change from
one to the other. This page describes the typical scenarios; the other pages give the details of
each component.

## Two questions

Each scenario answers two questions:

- **Who can reach the components?** Everything on one machine (the loopback), a closed network (a
  lab, a classroom, a cluster, a VPN), or an open network.
- **How far are the participants trusted?** One team; partners who follow the protocol but may try
  to learn from what they receive (*honest but curious*); participants who may send poisoned
  updates (*malicious*).

|  | one team | honest but curious partners | possibly malicious participants |
|---|---|---|---|
| **one machine** | [experimenting](#experimenting-on-one-machine), [automated runs](#automated-runs-without-a-browser) | — | [attack and defence studies](#attack-and-defence-studies) |
| **closed network** | [lab, classroom, cluster](#several-machines-on-a-closed-network) | [consortium over a VPN](#several-organisations) | [consortium over a VPN](#several-organisations) |
| **open network** | — | [several organisations](#several-organisations) | [several organisations](#several-organisations) |

The first question is about access: the [tokens](sessionmanager.md#access-tokens) and the
[encryption](multi-machine.md#encryption) of the manager and the agents. The second is not:
an admitted participant holds the session's tokens. Against it, Pybiscus has
[robust aggregation](robust-aggregation.md) for poisoned updates, server-side differential privacy
and the [privacy evaluation](privacy-evaluation.md) for curious partners.

## What the scenario decides

| | what changes |
|---|---|
| **connectivity** | who must reach whom ([table](multi-machine.md#who-calls-whom)), which ports are open, what a firewall, a NAT or a proxy cuts |
| **operation** | one operator for everything or one per site; a browser tab to launch a session; restarts |
| **resources** | memory and GPU shared by every process on one machine; network time per round across sites |
| **consistency of the settings** | how many forms are filled by how many operators: the [usual mistakes](#common-mistakes) grow with the sites |
| **meaning of the results** | simulated shares of one dataset (reproducible) or real data of each site (not reproducible) |
| **data governance** | what leaves each site, and where the reports are kept |
| **setup** | nothing on one machine; tokens, certificates and open ports across machines |

**What leaves a site**, in every scenario: the model updates (to the Flower server); the metrics of
each client, its number of examples included (to the server and the manager); the logs of its runs
(to the manager); its run configuration, whole, with its local paths (to the server agent, kept in
the server's reports). The training data never leaves it.

## Experimenting on one machine

**Use**: trying a model, a dataset, a strategy; preparing a session before spreading it.

**What Pybiscus brings**: a session from the [CLI](cli.md) and YAML files, or from the
[agents](agent.md) and the [session manager](sessionmanager.md) without writing YAML; the
consistency of the clients' settings (model, data, how the data is shared, number of clients,
rounds) set once in the session form; the data shared between simulated clients by configuration
(iid, dirichlet, shards) with seeds.

**Setup**: none. Every component listens on 127.0.0.1 and requires no token.

**Limits**:
- Memory bounds the number of clients: each is a process with its model and its data (cifar10, 20
  clients: about 1.2 GB each, see [robust-aggregation.md](robust-aggregation.md)). The GPU is shared
  by all of them.
- The results come from shares of one dataset: they compare strategies, they do not predict a
  session on real sites.

## Automated runs without a browser

**Use**: [campaigns](campaigns.md) comparing strategies, continuous integration
(`launch/ci/smoke.sh`), scripted sessions (`launch/uv/**`).

**What Pybiscus brings**: the server and the clients launched from YAML files, the campaign tool
running variants and seeds and gathering the results.

**Setup**: the CLI only; no manager, no agent.

**Limits**:
- A session of the manager is launched from the agents' pages, in a browser: the first launch is
  not scriptable. A [repeated session](sessionmanager.md#repeated-sessions) is then launched again
  by the manager alone.
- The CLI has no tokens: only the [TLS of Flower](multi-machine.md#flower) protects its traffic.
  Keep it on one machine or a closed network.

## Attack and defence studies

**Use**: measuring how a strategy resists malicious clients.

**What Pybiscus brings**: the `byzantine` client (sign flipping, scaling, ALIE, label flipping),
the robust strategies and decorators, campaigns with several seeds
([robust-aggregation.md](robust-aggregation.md)).

**Limits**: the attackers are simulated, on one machine; the participants are the operator's own.

## One shared machine

**Use**: a lab server or a compute node with several user accounts.

**Setup**: start the manager and the agents with `--require-token`: on 127.0.0.1, every account of
the machine reaches their ports.

## Several machines on a closed network

**Use**: the machines of a lab, a classroom, a test bench, containers or a cluster.

**What Pybiscus brings**: in addition to the above, the agents register with the manager as they
start; the manager's page shows who is there, their states, their metrics and a
[network view](sessionmanager.md) of the flows and their problems.

**Setup** ([multi-machine.md](multi-machine.md)):
- The manager and the server agent listen beyond the loopback (`--host 0.0.0.0`): they then require
  their tokens. Open their pages with the URL they print (`…?token=…`), give the session token to
  each agent's operator. The tokens are kept from one start to the next.
- The URLs name the machines, not `localhost`.
- Ports open: the manager, the server agent, the Flower server.
- Encryption: without it, the tokens and the configurations travel in clear. On a network shared
  with others, use the [built-in HTTPS](multi-machine.md#encryption) or a VPN.

**Limits**: one operator usually runs the whole session; several operators fill several forms
(see [common mistakes](#common-mistakes)).

## Several organisations

**Use**: sites that keep their data (hospitals, companies), each run by its own operator.

> **Status.** This scenario works: sessions with one manager per site, hierarchical ones included,
> run over HTTPS. They have been run with every site on one machine; a run across the machines of
> separate sites is still to come.
>
> **Its security guarantees are those of a closed network, not of an open one.** The web
> components run on the development server of Flask; the session token is shared by every
> participant, without expiry or revocation; Flower's TLS authenticates the server, not the
> clients. Keep the sites on a VPN, and do not expose the manager or the agents directly to the
> Internet.
>
> Work is in progress: hardening of the web components, then an invitation per site (a token of
> its own, bound to its name, revocable), the list of the expected sites against the present ones,
> and a check of the connectivity when a site joins.

**What Pybiscus brings**: each site's operator sees and checks its form before running; the session
form sets and locks what must be shared; [hierarchical sessions](hierarchical-session.md) give each
site its own manager, the upper level imposing its model, its data plugin and its number of rounds
on the lower ones.

**Setup**:
- HTTPS between the components, with a CA for the session and one certificate per machine (the
  key stays on its machine: [multi-machine.md](multi-machine.md#certificates)).
- A **VPN between the sites** (see the status above).
- In a hierarchical session, each link is its own scenario: inside a site, a closed network; between
  the sites, the managers of the lower levels reach the upper one, and each relay reaches the
  upper Flower server ([sessionmanager.md](sessionmanager.md#bouquets-of-a-hierarchical-session)).

**Against the participants**: robust aggregation if some may be malicious; differential privacy
if partners are curious, and the privacy evaluation to measure what a model reveals.

**Limits**: the results depend on who took part (a client registered after the launch gets no
share of a partition); no session can be reproduced exactly.

## Behind a tunnel or a reverse proxy

An SSH tunnel or a reverse proxy on the same machine lets a component listen on 127.0.0.1 while
others reach it: it then requires no token. **Start it with `--require-token`.** A reverse proxy
also has to pass the long requests (the runs' event streams, the links' waits of up to a minute).

## Common mistakes

The more sites and operators, the more of these; the checks of the forms and the manager's
network view catch some of them.

| mistake | effect |
|---|---|
| a URL left on `localhost` across machines (`manager_url`, `agent_url`, webhooks) | the component calls itself, without an error message |
| `server_host` of the session form left on `localhost` | each client looks for the server on its own machine |
| `server_host` not among the names of the server's certificate | the clients refuse the TLS connection |
| two sessions on one machine with the same Flower port | the second server refuses to start ([sessionmanager.md](sessionmanager.md)): each manager proposes its own port |
| a link `directory` between two machines | the relay and the lower server never see each other's files: use the `manager` transport |
| `min_clients` above the clients that will come | the first round never starts |
| an agent registering with another bouquet than the manager's | refused (or only warned, `--bouquet-mismatch warn`) |
