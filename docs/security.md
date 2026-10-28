# Security

What Pybiscus protects, what it does not, and how to deploy it accordingly. The
[usage scenarios](usage-scenarios.md) describe the environments; this page is their security side.
To report a vulnerability, see [SECURITY.md](../SECURITY.md).

## Scope

Two questions, as in the [usage scenarios](usage-scenarios.md#two-questions):

- **Who can reach the components** (the session manager, the agents, the Flower server)? The
  protections of the [network](#the-manager-and-the-agents) answer it.
- **How far are the participants trusted?** An admitted participant holds the session's tokens:
  against it, only the [federated learning defences](#against-the-participants) help.

In short: Pybiscus is made for one machine and for closed networks (a lab, a cluster, sites joined
by a VPN). It is **not designed yet to be exposed directly to the Internet** ([limits](#known-limits)).

## The manager and the agents

**Listening.** Every component listens on 127.0.0.1 by default. `--host 0.0.0.0` (or an address)
opens it to the network.

**Web server.** The manager and the agents run on [cheroot](https://cheroot.cherrypy.dev), a
production WSGI server: a pool of 64 threads (an open run monitor holds one), a client that stops
reading dropped after 30 s, TLS with `--tls-cert`. `--debug` switches to Werkzeug's development
server, for its reload on code change and its in-browser debugger, a Python console behind a PIN:
never on a machine others reach.

**Tokens** ([details](sessionmanager.md#access-tokens)):
- Required as soon as a component listens beyond the loopback; on the loopback, only with
  `--require-token` (a machine shared with other users). There is no option to do without them
  beyond the loopback.
- An **access token** per component, for its own pages and actions (the manager's is its
  administration token), and the manager's **session token**, given to the participants, accepted on
  the routes the agents and their runs call (registration, session parameters, webhooks).
- An **invitation** per agent, optional ([details](sessionmanager.md#agents-invitations)): a token
  of its own in place of the session token, bound to the agent's name and role, expiring, revocable;
  `--require-agent-invitation` refuses the agents without one. The same between the managers of a
  hierarchical session, per site ([details](sessionmanager.md#invitations)).
- A **call token** per agent, given to the manager at its registration: the agent proves with it
  that it is the one registered under its name when it asks the manager for its orders, and no
  other participant holds it. The manager calls no agent: the agents ask it for their orders (stop,
  relaunch), and a client's run configuration reaches the server agent through it.
- Kept in `.pybiscus-cache/tokens/`, readable by their owner only, from one start to the next.
  Given once in the URL (`…?token=…`), then kept by the browser in a cookie (`HttpOnly`,
  `SameSite=Lax`, `Secure` in HTTPS); compared in constant time.

**Requests from other sites.** A page of another site open in the operator's browser could drive
the components, even on 127.0.0.1:
- every request that changes something must carry the `X-Pybiscus` header, which a cross-site page
  cannot add without a CORS preflight: the agents grant none, the manager grants it to the local
  origins and to `--allow-origin`;
- without tokens, a component answers only requests naming the loopback (`localhost`, `127.x`,
  `::1`): a site whose name points to 127.0.0.1 (DNS rebinding) is refused, and so is a reverse proxy
  passing its own name;
- the manager's pages may be framed by their own origin only, an agent's by its own and by the
  manager it registered with (`frame-ancestors`); the manager takes a session form's values only from
  the frame of its ⚙ *Config* button, at the server agent's origin, and answers it at that origin.

**What the components receive** from the others is checked:
- an agent's URL must be `http://` or `https://` (it ends in the manager's page);
- the values a manager sets in the agents' forms are written into the page as data, never as code,
  and may not call an interpolation resolver (`${oc.env:…}`, which would read the agent's machine);
- a lower-level manager takes from its upper level only the model, its hyperparameters, the data
  plugin, the number of rounds and a valid link ([hierarchical sessions](sessionmanager.md#bouquets-of-a-hierarchical-session));
- requests are bounded at 16 MiB, a model put in the manager's mailbox at 1 GiB.

**Encryption.** Without TLS, tokens, configurations and logs travel in clear; a component listening
beyond the loopback without `--tls-cert` says so when it starts. HTTPS between the components: one
CA per session, one certificate per machine, the key never leaving its machine, the CA's key
protected by a password never written in the repository ([multi-machine.md](multi-machine.md#encryption)).

## Across sites

Until the [known limits](#known-limits) are lifted, the sites are joined by a **VPN**: no component
of Pybiscus faces the Internet, only the VPN's gateway, software made for it. The VPN bounds the
network, not the trust: every member reaches the ports it lets through, the other organisations'
machines included. Inside it, keep the tokens, use HTTPS unless every site trusts the others'
networks, and let through only the flows below.

**One session over several sites** (one manager, an agent per machine), from each client site:

| from | to | port (default) |
|---|---|---|
| client agent (its registration, its orders), its operator's browser, its runs (webhooks) | manager | 5555 |
| Flower client | Flower server | 3333 |

No flow enters a client site: the manager calls no agent, and the agents call no other agent
([who calls whom](multi-machine.md#who-calls-whom)). A client agent may listen on its loopback
when its operator's browser runs on its machine. The browser of the manager's operator also reaches
the server agent (5000) for the session form: a flow into the server's site when that browser is
elsewhere.

**A hierarchical session** (a manager per site): each site keeps its own closed network, and only
the links between the levels cross the VPN. With the `manager` link transport and each relay run
at the upper site, as for an [invited site](sessionmanager.md#invitations), **one flow** crosses it: from each lower manager to the upper one (its topology,
the constraints it receives, the link's mailbox). With a relay at the lower site (the `directory`
transport requires it), the relay's flows cross too: its agent, its operator's browser and its run
to the upper manager, its Flower client to the upper Flower server
([link transports](sessionmanager.md#bouquets-of-a-hierarchical-session)).

The ports are the defaults of the code: the manager's `--port` (5555), an agent's `--port` (5000),
the Flower server's `server_port` in the session form (proposed as 3333 + the manager's port −
5555). Each can be changed; the URLs that name the manager (registrations, webhooks) follow its port.
The manager's [network view](sessionmanager.md#network-view) lists the flows between machines of a
running session, with their ports (**⬇ flows (CSV)**): the list to give to whoever sets the VPN
or the firewall.

## Flower clients

In a session of the manager, the Flower server accepts only the clients of the session, one
connection each. At each session launch, the manager draws a key; a client's token is derived from
it and from its agent's name. Each agent asks the manager for its credential with its call token
(the session token, every participant's, gives none) and passes it to its run through the
environment, never in a configuration file: a client presents its name and token in the metadata of
its gRPC connection, the server checks them with the key and refuses a second connection under the
same name. A client launched outside the session, with a token of another session or under a name
already connected, is refused (`UNAUTHENTICATED`, said in both logs) and stops. A participant thus
opens no more Flower clients than it registered agents, which bounds the colluders of an attack
against the [robust aggregation](robust-aggregation.md). The repetitions of a session keep its
tokens. The legacy API of Flower takes no credential: Pybiscus adds it to its gRPC server and
channel (`pybiscus/flower/clientauth.py`).

## Code and data

- **No deserialisation that runs code**: models and weights are loaded as tensors only
  (`weights_only=True`, `allow_pickle=False`), YAML with `safe_load`.
- **A run is a fixed command** (`uv run pybiscus <server|client> launch <file>`), without a shell.
  A configuration selects among the plugins already loaded; it cannot load one.
- **A launch by order is opt-in**: an agent started with `--accept-launch` runs the configuration
  the manager's presets make of its launch configuration, which nobody reads first
  ([Launched by order](sessionmanager.md#launched-by-order)). The presets are the form's, the values
  calling an interpolation resolver ignored; the agent's log lists them.
- **A plugin is code**, run with the rights of the agent's user: the plugin manifest
  (`PYBISCUS_PLUGIN_CONF_PATH`, `pybiscus.env`) belongs to the operator of each machine. Load only
  plugins you trust.
- **What leaves a site**: the model updates, each client's metrics (its number of examples
  included), the logs of its runs, and its whole run configuration (its local paths too), which the
  server's reports keep ([details](usage-scenarios.md#what-the-scenario-decides)). The training data
  never leaves it.

## Against the participants

An admitted participant can send any update, and learns from the models it receives:

- **poisoned updates**: robust aggregation (clipping normalised by the size of the shares, Krum,
  Bulyan, FLTrust, FoolsGold...), measured against sign flipping, scaling, ALIE and label flipping
  ([robust-aggregation.md](robust-aggregation.md));
- **curious partners**: server-side differential privacy
  ([configuration.md](configuration.md#server-side-differential-privacy)), and the evaluation of what
  a model reveals of its training data ([privacy-evaluation.md](privacy-evaluation.md), under
  development).

## Known limits

They are why the guarantees are those of a closed network:

| limit | meanwhile |
|---|---|
| the session token is shared by every participant, without expiry or revocation: whoever holds it may register an agent under any name not invited | [invite the agents](sessionmanager.md#agents-invitations) (`--require-agent-invitation`): a token per agent, bound to its name and role, expiring, revocable; between the managers of a hierarchical session, [invite the sites](sessionmanager.md#invitations). Otherwise give it to the participants only, and restart the manager with a new token (`--session-token`) to revoke it |
| outside a session of the manager (CLI, campaigns), the Flower server does not authenticate its clients (its TLS authenticates the server only): whoever reaches its port may join a round | restrict its port with a firewall to the clients' addresses; in a Kubernetes cluster, with a NetworkPolicy ([example](containers.md#in-a-kubernetes-cluster)). In a session, [the clients are authenticated](#flower-clients) |
| in a session, a Flower client's token travels in clear without Flower's TLS: whoever reads the traffic may replay it | [Flower's TLS](multi-machine.md#flower) beyond one machine |
| an SSH tunnel to a component on 127.0.0.1 cannot be told from a local access | start it with `--require-token` |

## Checklist by scenario

Each scenario of the [usage scenarios](usage-scenarios.md), in the same order.

### Experimenting on one machine

Nothing: the defaults (listening on 127.0.0.1, no token needed). On a machine shared with other
user accounts, `--require-token` on the manager and the agents: every account reaches their ports.
[Scenario](usage-scenarios.md#experimenting-on-one-machine).

### Automated runs without a browser

No web component: Flower's [TLS](multi-machine.md#flower) for its traffic, a firewall on its port (a
NetworkPolicy in a Kubernetes cluster);
one machine or a closed network. [Scenario](usage-scenarios.md#automated-runs-without-a-browser).

### Attack and defence studies

As on one machine: the attackers are simulated, the participants are the operator's own.
[Scenario](usage-scenarios.md#attack-and-defence-studies).

### Several machines on a closed network

One agent per machine; `--host 0.0.0.0` on the manager and the agents (their tokens then
required); HTTPS if the network is shared with others; a firewall on the Flower port.
[Scenario](usage-scenarios.md#several-machines-on-a-closed-network).

### Several organisations

All of the above, HTTPS, a VPN between the sites letting through only the
[flows across sites](#across-sites); in a hierarchical session, each site
[invited](sessionmanager.md#invitations) by the upper level, started with `--require-invitation`; each agent
[invited](sessionmanager.md#agents-invitations) by its manager, started with `--require-agent-invitation`; robust aggregation if a participant may be malicious,
differential privacy if partners may be curious ([against the participants](#against-the-participants)).
[Scenario](usage-scenarios.md#several-organisations).

### Behind a tunnel or a reverse proxy

`--require-token`: the component listens on 127.0.0.1, so it would otherwise require no token.
[Scenario](usage-scenarios.md#behind-a-tunnel-or-a-reverse-proxy).
