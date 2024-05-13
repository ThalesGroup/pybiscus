# Pybiscus

A simple tool to perform Federated Learning on various models and datasets. Build on top of Flower (FL part), Typer (script and CLI parts) and Lightning/Fabric (ML part).

## Uses of Pybiscus

You have two ways of using Pybiscus. Either by cloning the repo and installing (via Poetry) all dependencies, and working on the code itself; or by just downloading the wheel and installing as a package.

### User Mode

The wheel in `dist/pybiscus-0.5.0-py3-none-any.whl` is the packaged version of Pybiscus. You can download it and do

```bash
pyenv local 3.9.12
python -m pip install virtualenv
python -m virtualenv .venv
source .venv/bin/activate
(.venv) pip install dist/pybiscus-0.4.0-py3-none-any.whl
```

The Pybiscus project comes with an handy app, dubbed pybiscus_app. You can test it directly as it is installed in your virtual env:

```bash
(.venv) pybiscus_app --help
```

this command will show you some documentation on how to use the app. There are three main commands:

- server is dedicated to the server side;

- client, to the client side;

- local is for local, classical training as a way to compare to the Federated version (if need be)

Note that the package is still actively under development, and even if we try as much as possible to not break things, it could happen!

To work, the app needs only config files for the server and the clients. Any number of clients can be launched, using the same command `client launch`.
or, now with config files (examples are provided in `configs/`):

```bash
pybiscus_app server launch path-to-config/server.yml
pybiscus_app client launch path-to-config/client_1.yml
pybiscus_app client launch path-to-config/client_2.yml
```

Here is the API for the server, for instance:
::: src.flower.server_fabric.launch_config

### Dev Mode

We strongly suggest the use of both pyenv and poetry.

- Pyenv is a tool to manage properly Python versions, and you can find install instructions here <https://github.com/pyenv/pyenv#installation>.

- Poetry is a dependency tool, way better than the usual "pip install -r requirements.txt" paradigm, and manages virtual environments too. It is easy to use, well documented, and the install instructions are here <https://python-poetry.org/docs/#installation>.

Once those tools are installed, clone the whole repo, and do

```bash
pyenv local 3.9.12  # the code has only been tested for this python version
poetry install
```

and you are good to go! We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a directory `datasets` to hold the data.

## Features

## Work in Progress

- [ ] Improving the Documentation part (Sphinx ?) and docstrings of the code.

- [ ] Implementation of the Simulation part of Flower.

- [ ] Organizing dependencies in pyproject.toml: dep from Typer/Flower/Fabric part (the core), dep from Paroma, dep from next data/model.

- [ ] Integration of Differential Privacy.

- [ ] Using only LightningDataModule, and getting rid of load_data.

- [x] Logging with tensorboard.

## Road Map

Here is a list of more mid/long term ideas to implement in Pybiscus for Federated Learning.
