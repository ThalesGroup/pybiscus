# Pybiscus: a flexible Federated Learning Framework

## Introduction

Pybiscus is a simple tool to perform Federated Learning on various models and datasets.
It aims at automated as much as possible the FL pipeline, and allows to add virtually any kind of dataset and model.

Pybiscus is built on top of Flower, a mature Federated Learning framework; Typer (script and CLI parts) and Lightning/Fabric for all the Machine Learning machinery.

You can simply test Pybiscus by downloading the latest wheel available and install it.

## Get started

You can simply test Pybiscus by downloading the latest wheel available in the dist folder and install it in a virtual environnement:
```bash
python -m pip install virtualenv
python -m virtualenv .venv
source .venv/bin/activate
(.venv) python -m pip install pybiscus_paroma-0.5.0-py3-none-any.whl
```

and you are good to go! The packages comes with an app named `pybiscus_paroma_app` that you can use in the virtual environment. You can then test if everything went well by launching a local training:
```bash
(.venv) pybiscus_paroma_app local train-config configs/local_train.yml
```

## Documentation

Documentation is available at [docs](docs/).

## Contributing

If you are interested in contributing to the Pybiscus project, start by reading the [Contributing guide](/CONTRIBUTING.md).

## Who uses Pybiscus

Pybiscus is on active development at Thales, both for internal use and on some collaborative projects. One major use is in the Europeean Project [PAROMA-MED](https://paroma-med.eu), dedicated to Federated Learning in the context of medical data distributed among several Hospitals.

## License

The License is Apache 2.0. You can find all the relevant information here [LICENSE](/LICENSE.md)

<!-- The chosen license in accordance with legal department must be defined into an explicit [LICENSE](https://github.com/ThalesGroup/template-project/blob/master/LICENSE) file at the root of the repository
You can also link this file in this README section. -->
