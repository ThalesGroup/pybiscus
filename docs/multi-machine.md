# Session spread over several machines

The defaults suit a session on one machine: every component listens on 127.0.0.1 and every URL
names `localhost`. A session spread over several machines needs the settings below; an URL left
on `localhost` breaks it without an error message (the component calls itself).

The session and its tokens are described in [sessionmanager.md](sessionmanager.md). Listening
beyond the loopback, the manager and the server agent require their tokens: open them with the URL
they print (`…?token=…`), and give the session token at each registration.

## Who calls whom

| caller | called | what |
|---|---|---|
| browser of the manager's operator | manager | manager page |
| browser of the manager's operator | **server agent** | session form, opened by the manager page |
| browser of each agent's operator | its agent | registration, configuration, run pages |
| browser of each agent's operator | manager | registration, waiting for the session launch |
| client agent | **server agent** | the client's run configuration |
| runs (server, clients) | manager | webhooks: logs, metrics, vignettes |
| Flower clients | **Flower server** | the training itself |

So the manager, the server agent and the Flower server must be reachable from the other machines;
a client agent only from its own operator's browser.

## Machine by machine

**Manager**
- `launch/session/run_manager.sh --host 0.0.0.0` (or the address of the right interface).
- Give the **session token** (🔑 button of the manager page, or printed at start) to the operator
  of each agent.
- The registration and waiting pages of an agent call the manager from the origin under which the
  agent's page was opened. Opened as `http://127.0.0.1:<port>` or `http://localhost:<port>` (its
  operator on its machine), it is allowed; opened under a host name, allow it:
  `--allow-origin http://site-a.example:5001` (one option per origin).

**Server agent**
- `--host 0.0.0.0`: the client agents and the browser of the manager's operator reach it.
- Its registration: `manager_url` = the manager's real URL, `agent_url` = the URL under which the
  others reach it (not `localhost`), and the session token.

**Client agents**
- May stay on 127.0.0.1 (their operator uses them from their machine).
- Their registration: `manager_url` = the manager's real URL, `agent_url` = their URL, the session
  token.

`manager_url`, `agent_url` and `session_token` can be written in the agent's registration
configuration (`--config`, see `pybiscus_agent_registration_config/`) to prefill the page.

## Session form

- **Flower server**: `server_listen_to` = *the whole internet* (the server listens on `[::]`),
  `server_host` = the server's host name as the clients reach it (the default `localhost` makes each
  client look for the server on its own machine), `server_port` open to the clients.
- **Webhooks**: the URLs of the `webhook` logger and metrics logger, and of the
  `visualize_model_layers` decorator, default to `http://localhost:5555/…`: they must name the
  manager. The runs launched by an agent present the session token it got at its registration.

## Ports to open

| port (default) | component | reached by |
|---|---|---|
| 5555 | manager | every browser, every run |
| 5000 | server agent | the manager's operator's browser, the client agents |
| 3333 | Flower server | the Flower clients |

## Encryption

HTTP between the manager and the agents is not encrypted: the tokens, the configurations and the
logs travel in clear. Between machines, go through an SSH tunnel, a VPN, or an HTTPS reverse proxy
in front of the manager and the server agent. The Flower traffic has its own option: `ssl` of the
session form (`https`), with the certificates of `certificates/`.
