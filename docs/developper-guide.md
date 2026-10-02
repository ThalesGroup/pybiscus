# How to dev

If you want to help develop Pybiscus, by adding for instance other datasets or Torch modules, there are a few "rules" to follow and a few tools to use. Those are meant to help better develop Pybiscus, not to be an hindrance for a newly Python user wanted to try and test Pybiscus!

This guide is meant to be as concise as possible, but of course no one can cover it all.

## Tools

Here is a short list of tools used to develop Pybiscus. Not all are mandatory, but they are all helpful. In fact, now, you need only once : uv ;-).

### uv

**uv** is a tool to manage properly Python versions, package depencies and scripts execution. You can find install instructions here https://docs.astral.sh/uv/getting-started/installation/.


Once those tools are installed, clone the all repo, and do
```bash
uv sync
```

and you are good to go !
This all-in-one command installs Python 3.12 if needed, creates a virtual environment (`.venv`) and installs the dependencies at their locked versions (`uv.lock`).

## Conventions

### Configuration models

Every configuration is a Pydantic model, validated before anything runs (`pybiscus server|client
check`) and turned into the agents' forms:

- `model_config = ConfigDict(extra="forbid")`: a misspelt key is refused, not ignored;
- every field with `Field(description=..., ...)`: the description is the form's tooltip, the
  constraints (`ge`, `gt`, `le`, `lt`) are checked at `check`;
- a plugin's configuration is a `name: Literal[...]` / `config:` pair whose `name` equals its
  registry key (checked at start-up); see [Plugins](plugins.md) for the metadata it may declare.

### Logging, not print

Use the configurable logger instead of `print`:

```python
import pybiscus.core.pybiscus_logger as logm

logm.console.log(config)
```

By default it is Rich's console; it can be multiplexed, notably to the session manager's webhook.

### Comments

Names describe what the code does; a comment says why a decision is not obvious (a trap avoided, a
hidden constraint, a surprising behaviour), never what the next lines do.

### Validating a change

There is no unit test suite: behaviour depends on the plugins and the configurations, across
several processes. Validate a change by `check` on the configurations it touches and by real runs:
the `launch/uv/` scripts, a session with the agents, or a campaign
([Campaigns](campaigns.md)) when results must be compared.

`launch/ci/smoke.sh` replays the basic ones and fails with a non-zero exit code, for a check before
a release or in a pipeline:

```bash
./launch/ci/smoke.sh                       # check + run
./launch/ci/smoke.sh build container-run   # the container images, then the same run in containers
```

- `check`: every server and client configuration of `configs/` passes `check`;
- `run`: the mnist demo, server and two clients on CPU, 2 rounds on 2000 examples, on a free port;
- `build`: the two container images ([Containers](containers.md));
- `container-run`: the same run in containers of the pybiscus image.

Each run works in a directory of its own (printed at the end, with the logs), not in the
repository's `experiments/`.

## Others

We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a
directory `datasets` to hold the data (both are ignored by git).
