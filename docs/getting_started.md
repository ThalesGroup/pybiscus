
# Pybiscus

A simple tool to perform Federated Learning on various models and datasets. Build on top of Flower (FL part), Typer (script and CLI parts) and Lightning/Fabric (ML part).


## Key features

* a ***CLI*** built on Typer: to launch a server or a client, it is as simple as invoking the pybiscus app! Everything needed is written in config files, as you can find in the configs directory. **No code to change, juste YAML files!**
* a ***web-based agent*** that provides an interactive interface for configuring and launching pybiscus from your browser. **No YAML files to write, just click !**
* all thing related to the Machine Learning parts is handled by Lightning and Fabric, cornerstones of the PyTorch ecosystem. This allows to separate the "Federated" part (i.e. senfin/receiving/aggragating the weights; done by FLower) from the specifics of the models and the data themselves. The Flower part is as much as possible agnostic from the ML part.
* as it is, the Server part will log in tensorboards all losses and metrics sent by the Clients (both on fit and evaluate), and also the loss and metrics computed by the Server if global test dataset is provided. This allows to follow the good process of the Federated Learning session.
* the final model is saved on the Server side
* the structure of the code is meant to be as modular as possible. If you need to add other datasets and/or models, please have a look at [how-to](how-to.md).

## Install Pybiscus
After cloning the repo and installing (via uv) all dependencies, tou have to extend you PATH with the command:
```bash
source ./extend_path.sh
```

### Command Line Interface Mode
```
The Pybiscus project comes with an handy app, dubbed pybiscus. You can test it directly :
```bash
pybiscus --help
```

this command will show you some documentation on how to use the app. There are three main commands:
 - server is dedicated to the server side;
 - client, to the client side;
 - local is for local, classical training as a way to compare to the Federated version (if need be)

Note that the package is still actively under development, and even if we try as much as possible to not break things, it could happen!

To work, the app needs only config files for the server and the clients. Any number of clients can be launched, using the same command `client launch`.
or, now with config files (examples are provided in `configs/`):
```bash
pybiscus server launch path-to-config/server.yml
pybiscus client launch path-to-config/client_1.yml
pybiscus client launch path-to-config/client_2.yml
```

You can use also the command `client check` to verify before-hand that the configuration file satisfies the Pydantic constraints.
