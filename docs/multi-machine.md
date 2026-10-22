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
| browser of each agent's operator | manager | registration, waiting for the session launch (the run starts from this page: keep it open) |
| manager | agents | state and stop of their runs, relaunch of a repeated session |
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
- Open the manager's page under the name its agents registered it with (`manager_url`), or under
  `localhost` / `127.0.0.1` on its machine: the server agent lets only these frame its session form.

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

Without TLS, the tokens, the configurations and the logs travel in clear: a manager or an agent
listening beyond the loopback without `--tls-cert` says so when it starts. Either use the built-in
TLS below, or an SSH tunnel, a VPN, or an HTTPS reverse proxy in front of the manager and the
server agent. Behind a tunnel or a proxy on its machine, a component listening on 127.0.0.1 needs
`--require-token` ([usage scenarios](usage-scenarios.md#behind-a-tunnel-or-a-reverse-proxy)).

### Certificates

One certificate authority (CA), in `certificates/`, and one certificate per machine: the manager
and the agents of a machine share it, and so does the Flower server running there.

1. Once, where the CA is kept: edit `certificates/set_env.sh` (names of the organisation, and
   `rootCApass`: the demo's password protects nothing), then `cd certificates && ./gen_from_env.sh`.
   It refuses to replace an existing CA (`FORCE_NEW_CA=1` forces it): a new CA invalidates every
   certificate it signed.
2. For each machine:
   - its key stays on it: there, `certificates/gen_component_csr.sh site-a.example.org`; send the
     request `components/site-a.example.org/site-a.example.org.csr` to whoever holds the CA, who
     runs `certificates/sign_component_csr.sh site-a.csr site-a.example.org "IP:10.0.0.5"` and sends
     back `components/site-a.example.org/site-a.example.org.crt` and `ca/ca.crt`;
   - for a demo, or machines of one owner: `certificates/gen_component_cert.sh <name> [entries]`
     does both where the CA is.

   The certificate is valid for the given name, `localhost`, `127.0.0.1`, `::1` and the extra
   entries: every URL naming this machine must use one of them.

What each machine of a session needs:

| machine | files | used by |
|---|---|---|
| where the CA is kept | `ca/ca.key` (never copied), `ca/ca.crt` | `sign_component_csr.sh` |
| manager | its certificate and key, `ca/ca.crt` | `--tls-cert`, `--tls-key`, `--tls-ca` |
| server agent | its certificate and key, `ca/ca.crt` | `--tls-*`, and the Flower server (below) |
| client agent | `ca/ca.crt`; its certificate and key if it listens beyond the loopback | `--tls-ca`, the Flower client (below) |

### Components

```bash
launch/session/run_manager.sh --host 0.0.0.0 --tls-ca certificates/ca/ca.crt \
  --tls-cert certificates/components/site-m.example.org/site-m.example.org.crt \
  --tls-key  certificates/components/site-m.example.org/site-m.example.org.key
pybiscus_agent --host 0.0.0.0 --port 5000 --tls-ca certificates/ca/ca.crt --tls-cert … --tls-key …
```

- `--tls-cert` and `--tls-key`: the component serves HTTPS; the URLs it prints, and gives to the
  managers it is linked to, start with `https://`.
- `--tls-ca`: the component, and the runs it launches, trust this CA besides the usual authorities
  (a bundle written in `.pybiscus-cache/tls/ca-bundle.pem`, exported as `REQUESTS_CA_BUNDLE`).
  Every agent needs it, even one serving HTTP, to reach a manager in HTTPS; without it, the agent's
  log says that the manager's certificate is not trusted.
- `manager_url`, `agent_url`, the webhook URLs of the session form and the `--allow-origin`
  origins start with `https://`.
- **Beyond the loopback, all in HTTPS**: browsers block an HTTP page inside an HTTPS one, so the
  manager page could not show the session form of a server agent in HTTP. The manager warns at the
  registration of an agent reached in HTTP on another machine; agents reached at `localhost` may
  stay in HTTP.
- Check a component from another machine: `curl --cacert certificates/ca/ca.crt
  https://site-m.example.org:5555/pybiscus-session/manage`.

### Browsers

The browser of each operator must trust `ca/ca.crt`, else it shows a security warning:
- Firefox: settings, *Privacy & Security*, *Certificates*, *View Certificates*, *Authorities*,
  *Import* (trust it to identify websites);
- Chrome and Edge on Windows, also for a session run in WSL: `certutil -addstore -user Root ca.crt`;
- Chrome on Linux: `certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n Pybiscus -i ca.crt`
  (package `libnss3-tools`);
- macOS: *Keychain Access*, import into *System*, *Always Trust*.

Remove it after the session when the CA was made for a demo.

### Flower

The Flower traffic is encrypted on its own, from the session form: choose `server_protocol:
https`. The configuration page of the server and of each client then has an `ssl` section to
fill, on each agent's machine:

- server agent: `root_certificate_path` = `ca/ca.crt`, `server_certificate_path` and
  `server_private_key_path` = the certificate and the key of its machine, the same files as its
  `--tls-cert` and `--tls-key`;
- each client agent: `secure_cnx` on, `root_certificate` = `ca/ca.crt`;
- `server_host`, in the session form, is the name the clients reach the server at: one of the names
  of the server machine's certificate (`localhost` only for a session on one machine).

The paths are read on the agent's machine; `${root_dir}` is the directory the agent was started
from, e.g. `${root_dir}/certificates/ca/ca.crt` for an agent started at the root of the repository.
The server logs `SSL is enabled` when it starts. Outside a session, the demo of
`configs/cifar10_cnn/distributed/ssl/` does the same ([cli.md](cli.md#encrypting-the-flower-traffic-ssl)).

Flower's TLS encrypts the traffic and authenticates the server only: the Flower clients of
Pybiscus present no certificate (the legacy API takes none), so whoever reaches the port can join
as a client; restrict it with a firewall. `gen_from_env.sh` no longer makes client certificates
(`NUM_CLIENTS` of `set_env.sh`, 0 by default).
