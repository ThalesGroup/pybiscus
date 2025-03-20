# How to dev

If you want to help develop Pybiscus, by adding for instance other datasets or Torch modules, there are a few "rules" to follow and a few tools to use. Those are meant to help better develop Pybiscus, not to be an hindrance for a newly Python user wanted to try and test Pybiscus!

This guide is meant to be as concise as possible, but of course no one can cover it all :)

## Tools

Here is a short list of tools used to develop Pybiscus. Not all are mandatory, but they are all helpful.

### Pyenv

**Pyenv** is a tool to manage properly Python versions, and you can find install instructions here https://github.com/pyenv/pyenv#installation.

###  Poetry

**Poetry** is a dependency tool, way better than the usual "pip install -r requirements.txt" paradigm, and manages virtual environments too. It is easy to use, well documented, and the install instructions are here https://python-poetry.org/docs/#installation.

Once those tools are installed, clone the all repo, and do
```bash
pyenv local 3.9.12  # the code has only been tested for this python version
poetry install --sync -E parom --with=dev,docs
```

and you are good to go!

### Pre-commit

**Pre-commit** allows for ensuring that formatting and linting rules are conformed at each new commit, merge and the like. No need then to call Ruff or Black yourself, just let pre-commit do that for you! You can find more informations here https://pre-commit.com

Once installed, do
```bash
poetry run pre-commit install
```

### Linters

**Black**, **Ruff** are formatting and linting tools

## Others

We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a directory `datasets` to hold the data.

### Pydantic Validation

[TODO]

### Print statements

Please use `console.log` instead of print! The Rich Console is really better at this.
