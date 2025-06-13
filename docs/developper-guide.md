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
This all-in-one command creates a virtual environment, downloads and installs the dependant packages, and creates an uv.lock file.

### Pre-commit

**Note: deprecated* as we switched to uv*


~~**Pre-commit** allows for ensuring that formatting and linting rules are conformed at each new commit, merge and the like. No need then to call Ruff or Black yourself, just let pre-commit do that for you! You can find more informations here~~ https://pre-commit.com

~~Once installed, do~~
~~poetry run pre-commit install~~

### Linters

**Black**, **Ruff** are formatting and linting tools

## Others

We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a directory `datasets` to hold the data.

### Pydantic Validation

[TODO]

### Print statements

Please use `logm.console.log` instead of print !

```python
import pybiscus.core.pybiscus_logger as logm

logm.console.log(config)
```

It will use a configurable logger. By default, the Rich Console which is really far better at this in CLI mode.
However, it can be configured to support multiplexing, notably enabling output to be sent to a supervision webhook for GUI mode

