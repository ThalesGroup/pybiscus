# Welcome to Pybiscus!

You can find here a (still quite short) documentation on how to use and adapt Pybiscus. The tool is aimed at being modular and as simple as possible.

## Project layout

Here are the main directories of the Pybiscus project:

* the src directory - the core of Pybiscus:
    * src/flower contains new implementation of Client, Server and Strategies provided by Flower, using Fabric in order to be agnostic to hardware, precision and the like.
    * src/ml contains both data and models. This is where you can add simply your own dataset or model.
* configs - contains only YAML configuration files. In order to change the behaviour of your client, model etc, do not change the code - change the config!
* container: everything related to the build of the Docker image and its use thanks to scripts.
* main.py: the entrypoint of Pybiscus. Gather all three main commands: server, client and local-train.
* docs: last but not least, the present documentation

We strongly suggest to create some other directories:

* experiments: to hold checkpoints, tensorboards and such.
* datasets: this is self explanatory!
