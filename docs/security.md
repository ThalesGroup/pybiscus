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

**Tokens** ([details](sessionmanager.md#access-tokens)):
- Required as soon as a component listens beyond the loopback; on the loopback, only with
  `--require-token` (a machine shared with other users). There is no option to do without them
  beyond the loopback.
- An **access token** per component, for its own pages and actions (the manager's is its
  administration token), and the manager's **session token**, given to the participants, accepted on
  the routes the other components call (registration, session parameters, webhooks, a client's run
  configuration).
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

## Code and data

- **No deserialisation that runs code**: models and weights are loaded as tensors only
  (`weights_only=True`, `allow_pickle=False`), YAML with `safe_load`.
- **A run is a fixed command** (`uv run pybiscus <server|client> launch <file>`), without a shell.
  A configuration selects among the plugins already loaded; it cannot load one.
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
| the manager and the agents run on Flask's development server | keep them out of reach of the Internet (VPN) |
| the session token is shared by every participant, without expiry or revocation: whoever holds it may register under any name | give it to the participants only; restart the manager with a new token (`--session-token`) to revoke it |
| the Flower server does not authenticate its clients (its TLS authenticates the server only): whoever reaches its port may join a round | restrict its port with a firewall to the clients' addresses |
| an SSH tunnel to a component on 127.0.0.1 cannot be told from a local access | start it with `--require-token` |
| the manager calls the agents (stop, relaunch): it must reach them | place it where it reaches them |

Work in progress: hardening of the web components, then an invitation per site (a token of its own,
bound to its name, revocable), the list of the expected sites against the present ones, and a check of
the connectivity when a site joins.

## Checklist by scenario

Each scenario of the [usage scenarios](usage-scenarios.md), in the same order.

### Experimenting on one machine

Nothing: the defaults (listening on 127.0.0.1, no token needed). On a machine shared with other
user accounts, `--require-token` on the manager and the agents: every account reaches their ports.
[Scenario](usage-scenarios.md#experimenting-on-one-machine).

### Automated runs without a browser

No web component: Flower's [TLS](multi-machine.md#flower) for its traffic, a firewall on its port;
one machine or a closed network. [Scenario](usage-scenarios.md#automated-runs-without-a-browser).

### Attack and defence studies

As on one machine: the attackers are simulated, the participants are the operator's own.
[Scenario](usage-scenarios.md#attack-and-defence-studies).

### Several machines on a closed network

One agent per machine; `--host 0.0.0.0` on the manager and the agents (their tokens then
required); HTTPS if the network is shared with others; a firewall on the Flower port.
[Scenario](usage-scenarios.md#several-machines-on-a-closed-network).

### Several organisations

All of the above, HTTPS, a VPN between the sites ([known limits](#known-limits)); robust
aggregation if a participant may be malicious, differential privacy if partners may be curious
([against the participants](#against-the-participants)).
[Scenario](usage-scenarios.md#several-organisations).

### Behind a tunnel or a reverse proxy

`--require-token`: the component listens on 127.0.0.1, so it would otherwise require no token.
[Scenario](usage-scenarios.md#behind-a-tunnel-or-a-reverse-proxy).
