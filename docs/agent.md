
# Agent: configuring and launching from the browser

Install Pybiscus first ([Getting started](getting_started.md#installation)).

The agent (`pybiscus_agent`) is a small web application, one per site: it generates the server or
client configuration form from the configuration models (every plugin included, every field
described on hover), checks the configuration and launches the server or the client. It can be
used alone, as below, or driven by the session manager
([Session using the manager](sessionmanager.md)).

Launch the server agent, then open the URL it prints (`http://localhost:5000/server/config`,
with `?token=…` when it requires one):

```bash
./launch/agent/cli/5000.sh
```

![Server web app](images/server_webapp.png "Server web app")

Launch the client agents, and open `http://localhost:5001/client/config` and
`http://localhost:5002/client/config`:

```bash
./launch/agent/cli/5001.sh
./launch/agent/cli/5002.sh
```

![Client web app](images/client_webapp.png "Client web app")

On each form:
- **Check** validates the configuration; **Execute** (enabled once it is checked)
  launches the server or the client. Launch the server first, then the clients.
  A refused configuration shows each error in red under its field, or on the block it is about
  (an unknown key, a whole section); the form opens the section of the first one. An error the form
  has no place for, or a failure that is not a validation error (a missing plugin), is shown under
  the buttons.
- **Save to disk** downloads the YAML file, to use with the [CLI](cli.md).
- On the server: **Pin** keeps the current form for the next visits, **Blank**
  returns to the defaults; a badge shows where the displayed configuration comes from (pinned, or
  generated and not pinned).
- An optional field shows *optional* and a box next to its name: ticked, it takes a value; unticked,
  it is left unset.
- The ⚙ panel sets the display (tabs, compact lists, theme).

Once launched, the page switches to the run monitor: the run's state and its log lines, live,
with a button to stop it.

![Run monitor](images/agent_run_monitor.png "Run monitor")

The agent listens on 127.0.0.1 by default; see [Access tokens](sessionmanager.md#access-tokens)
and [Session spread over several machines](multi-machine.md) to reach it from elsewhere.
