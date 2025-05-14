![Pybiscus logo](/pybiscus/assets/images/logo_pybiscus.png)

# Pybiscus: a flexible Federated Learning Framework

## Introduction

Pybiscus is a simple tool to perform Federated Learning on various models and datasets.
It aims at automated as much as possible the FL pipeline, and allows to add virtually any kind of dataset and model.

Pybiscus is built on top of Flower, a mature Federated Learning framework; Typer (script and CLI parts) and Lightning/Fabric for all the Machine Learning machinery.

It is managed using the uv package manager

The architecture is built around a plugin system and extensible hooks, and we are continuously evolving the framework to maximize flexibility and adaptability across all aspects of the federated learning process.

In addition to the pybiscus command-line application, we have introduced two key tools:

- a lightweight client *agent* that dynamically generates the configuration interface;

- a *session manager* that synchronizes configuration of the server and clients, and handles the orchestration of the training session.

## Get started using uv 

uv is a python project and package manager ( https://github.com/astral-sh/uv )

extend your user's path to include the bin directory

```bash

source ./extend_path.sh
```

download the required packages

```bash

uv sync
```

You can find example launch scripts in ./launch/uv subdirectories

## Documentation

Documentation is available at [docs](docs/index.md).

## Contributing

If you are interested in contributing to the Pybiscus project, start by reading the [Contributing guide](/CONTRIBUTING.md).

## Who uses Pybiscus

Pybiscus is on active development at Thales, both for internal use and on some collaborative projects. One major use is in the Europeean Project [PAROMA-MED](https://paroma-med.eu), dedicated to Federated Learning in the context of medical data distributed among several Hospitals.

## License

The License is Apache 2.0. You can find all the relevant information here [LICENSE](/LICENSE.md)

<!-- The chosen license in accordance with legal department must be defined into an explicit [LICENSE](https://github.com/ThalesGroup/template-project/blob/master/LICENSE) file at the root of the repository
You can also link this file in this README section. -->
