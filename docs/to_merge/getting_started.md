# Pybiscus

A simple tool to perform Federated Learning on various models and datasets. Build on top of Flower (FL part), Typer (script and CLI parts) and Lightning/Fabric (ML part).


## Key features

* a CLI built on Typer: to launch a server or a client, it is as simple as invoking the pybiscus app! Everything needed is written in config files, as you can find in the configs directory. No code to change, juste YAML files!
* all thing related to the Machine Learning parts is handled by Lightning and Fabric, cornerstones of the PyTorch ecosystem. This allows to separate the "Federated" part (i.e. senfin/receiving/aggragating the weights; done by FLower) from the specifics of the models and the data themselves. The Flower part is as much as possible agnostic from the ML part.
* as it is, the Server part will log in tensorboards all losses and metrics sent by the Clients (both on fit and evaluate), and also the loss and metrics computed by the Server if global test dataset is provided. This allows to follow the good process of the Federated Learning session.
* the final model is saved on the Server side
* the structure of the code is meant to be as modular as possible. If you need to add other datasets and/or models, please have a look at [how-to](how-to.md).

## Uses of Pybiscus
You have two ways of using Pybiscus. Either by cloning the repo and installing (via Poetry) all dependencies, and working on the code itself; or by just downloading the wheel and installing as a package.

### User Mode
The wheel in `dist/pybiscus-0.5.1-py3-none-any.whl` is the packaged version of Pybiscus. You can download it and do
```bash
pyenv local 3.9.12
python -m pip install virtualenv
python -m virtualenv .venv
source .venv/bin/activate
(.venv) pip install dist/pybiscus-0.5.1-py3-none-any.whl
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

You can use also the command `client check` to verify before-hand that the configuration file satisfies the Pydantic constraints.

### Dev Mode

We strongly suggest the use of both pyenv and poetry.

* Pyenv is a tool to manage properly Python versions, and you can find install instructions here https://github.com/pyenv/pyenv#installation.

* Poetry is a dependency tool, way better than the usual "pip install -r requirements.txt" paradigm, and manages virtual environments too. It is easy to use, well documented, and the install instructions are here https://python-poetry.org/docs/#installation.

Once those tools are installed, clone the all repo, and do
```bash
pyenv local 3.9.12  # the code has only been tested for this python version
poetry install --sync -E paroma --with=dev,docs
```

and you are good to go! We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a directory `datasets` to hold the data.
