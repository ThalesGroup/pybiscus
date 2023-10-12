# Pybiscus

A simple tool to perform Federated Learning on various models and datasets. Build on top of Flower (FL part), Typer (script and CLI parts) and Lightning/Fabric (ML part).

## Uses of Pybiscus
You have two ways of using Pybiscus. Either by cloning the repo and installing (via Poetry) all dependencies, and working on the code itself; or by just downloading the wheel and installing as a package.

### User Mode
The wheel in `dist/pybiscus-0.3.2-py3-none-any.whl` is the packaged version of Pybiscus. You can download it and do
```bash
pyenv local 3.9.12
python -m pip install virtualenv
python -m virtualenv .venv
source .venv/bin/activate
(.venv) pip install dist/pybiscus-0.3.2-py3-none-any.whl
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

To work, the app needs only config files for the server and the clients. Any number of clients can be launched, using the same command `client launch-config`.
or, now with config files (examples are provided in `configs/`):
```bash
pybiscus_app server launch-config path-to-config/server.yml
pybiscus_app client launch-config path-to-config/client_1.yml
pybiscus_app client launch-config path-to-config/client_2.yml
```

### Dev Mode

We strongly suggest the use of both pyenv and poetry. 

* Pyenv is a tool to manage properly Python versions, and you can find install instructions here https://github.com/pyenv/pyenv#installation. 

* Poetry is a dependency tool, way better than the usual "pip install -r requirements.txt" paradigm, and manages virtual environments too. It is easy to use, well documented, and the install instructions are here https://python-poetry.org/docs/#installation.

Once those tools are installed, clone the all repo, and do
```bash
pyenv local 3.9.12  # the code has only been tested for this python version
poetry install
```

and you are good to go! We suggest to create a directory `experiments` to hold checkpoints and other artefacts and a directory `datasets` to hold the data.

## Docker

To build the image (which is quite heavy as of now), do the following
```bash
cd container
docker build . -t pybiscus:app.v0.3.2
```



If you are working under a proxy, you might need to add some argument for the buid

```bash
cd container
docker build \
--build-arg http_proxy=$HTTP_PROXY \
--build-arg https_proxy=$HTTPS_PROXY \
--build-arg no_proxy=$NO_PROXY \
. -t pybiscus:app.v0.3.2
```

Then, again only if you have to go through a proxy for internet access, then to download the data the different containers will need and internet access.
So you need to set the file `~/.docker/config.json` with the proxy config

For the client to be able to communicate with the server you need to add "server"
to ne noProxy config.

```json
{
        "proxies":{
                "default":{
                        "httpsProxy": "your_httpsProxy",
                        "httpProxy": "your_httpProxy",
                        "noProxy": "your_noProxy,server",
                }
        }
}
```

and voila! The docker image is aimed at running only the pybiscus_app itself. In order to facilitate the use of docker (which can be quite verbose), some scripts are available in container/scripts. To launch a local training, you just need to update `container/scripts/launch_local_train.sh` and `container/configs/local_train.yml` according to where are located your datasets and such. Then, simply run
```bash
bash container/scripts/launch_local_train.sh
``` 

It is as simple as running
```bash
docker run -t --gpus device=(some_device) -v "$(pwd)":/app/datasets pybiscus:app --help
```

to get the help of the app. The short version is, `docker run -t pybiscus:app` is equivalent to running `pybiscus_app`. As for the app itself, the docker image can launch either client, server or local components.

To launch a "true" Federated learning, you need first to create a docker network for the containers to communicate:
```bash
docker network create federated
```

then 
```bash
bash container/scripts/launch_server.sh
```

followed by (in other terminal)
```bash
bash container/scripts/launch_client_1.sh
```
and 
```bash
bash container/scripts/launch_client_2.sh
```

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
