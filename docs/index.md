![Pybiscus logo](/pybiscus/assets/images/logo_pybiscus.png)

# Welcome to Pybiscus!

You can find here a short documentation on how to use and adapt Pybiscus. The tool is aimed at being modular and as simple as possible.

## Project layout

Here are the main directories of the Pybiscus project:

* the pybiscus directory - the core of Pybiscus:
    * pybiscus/flower contains new implementation of Client, Server and Strategies provided by Flower, using Fabric in order to be agnostic to hardware, precision and the like.
    * pybiscus/ml may host data and models, but the recommanded way is in pybiscus-plugins (see how-to for plugin development). 
* configs - contains only YAML configuration files. In order to change the behaviour of your client, model etc, do not change the code - change the config!
* container: everything related to the build of docker/podman images.
* launch: scripts to launch session, either inline with uv or using containers, with variations on the used models, network configuration, ssl optional usage ...
* main.py: the entrypoint of Pybiscus. Gather all three main commands: server, client and local-train.
* docs: last but not least, the present documentation

We strongly suggest to create some other directories:

* experiments: to hold checkpoints, tensorboards and such.
* datasets: this is self explanatory!
