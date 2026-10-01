# Plugins information

# Plugin Development

## Model and Data Provider Development

For detailed instructions on creating custom models and data providers, refer to the [PyBiscus Integration Guide](pybiscus_model_guide.md).

This document covers plugin directory structure and registration mechanisms...


![Pybiscus architecture](images/pybiscus_architecture.svg)

Their source code can be located in several locations according to their type: 
- in a specific package pybiscus source tree (for those of general interest)
- in their specific source tree, referenced by category in the plugin definition yaml file. 
Meaning you have the ability to embed code originating from an external repository.

They shall implement an interface defined in *pybiscus.interfaces* package.
Their package shall provide a specific entry point *get_modules_and_configs()* in its *__init__.py* file that is checked at launch for a run-time discovery. [More technical info in How-to](how-to.md)

Abbreviated packages representation used in the following array :
- ⚡.🔥 lightning.pytorch
- 🌺.🤖 pybiscus\.ml
- 🌺.🌼 pybiscus.flower
- 🌺.🔘 pybiscus.core
- 🌺.🔌.🔘 pybiscus.interfaces.core
- 🌺.🔌.🌼 pybiscus.interfaces.flower

|Implemented interface|Source tree location|Plugin type definition|
|:--------------------|:-------------------|:--------------------:|
|⚡.🔥.LightningDataModule|🌺.🤖.data|data|
|⚡.🔥.LightningModule|🌺.🤖.models|model|
|🌺.🔌.🔘.metricsloggerfactory.MetricsLoggerFactory|🌺.🔘.metricslogger|metricslogger|
|🌺.🔌.🔘.logger.LoggerFactory|🌺.🔘.logger|logger|
|🌺.🔌.🌼.fabricstrategyfactory.FabricStrategyFactory|🌺.🌼.strategy|strategy|
|🌺.🔌.🌼.strategydecorator.StrategyDecorator|🌺.🌼.strategydecorator|strategydecorator|
|🌺.🔌.🌼.clientfactory.ClientFactory|🌺.flower_fabric.client|client|
|🌺.🔌.🌼.flowerfitresultsaggregator.FlowerFitResultsAggregator|🌺.🌼.flowerfitresultsaggregator|flowerfitresultsaggregator|
|🌺.🔌.🌼.resultmodifier.ResultModifier|🌺.🌼.resultmodifier|resultmodifier|

## Loading: what stops Pybiscus, what does not

At start-up, every module of the manifest is imported and its `get_modules_and_configs()` called.

- A plugin whose **third-party dependency is missing** is skipped with a warning
  (`⚠️ 🧩 Plugin '…' skipped: missing dependency '…'`): the other plugins keep working, and a
  configuration that names the skipped one is refused with the list of skipped plugins.
  `PYBISCUS_PLUGINS_STRICT=1` turns this into an error.
- Everything else is an error that stops the command (exit code 78) with its cause: a manifest
  that cannot be read, a path that does not exist, a plugin not found or failing to import, a
  plugin **shadowed** by another module of the same name (plugins are top-level modules: name
  yours so that no installed package has that name), a registry key that differs from its
  configuration's `name` `Literal`, two plugins registering the same key.
- `PYBISCUS_PLUGINS_VERBOSE=1` prints the details of the loading.

## Metadata a plugin's configuration may declare

Class attributes (`ClassVar`) of the configuration classes, read by the forms and the validation:

| attribute | on | effect |
|---|---|---|
| `PYBISCUS_ALIAS` | the `name`/`config` class | label shown in the forms instead of the class name |
| `PYBISCUS_GROUP` | the `name`/`config` class | family the option is grouped under in long lists (strategies: Averaging, Server optimizers, Robust aggregation...; decorators: Metrics, Saving, Robustness...) |
| `PYBISCUS_CONFIG` | a nested configuration class | name of its section in the forms (`config`, `train`, `server_run`...) |
| `PYBISCUS_DESCRIPTIONS` | an `Enum` (set after the class) | description of each value, shown on hover |
| `PYBISCUS_INCOMPATIBLE_WITH` | a strategy decorator | decorators it cannot be combined with in a pipeline: refused at `check` |
| `PYBISCUS_AFTER` | a strategy decorator | decorators that must come before it in the pipeline: refused at `check` otherwise |
| `PYBISCUS_SERVER_SECTIONS` | a data plugin's configuration | sections the server reads (`test` and `privacy` by default): the server warns when another one differs from its defaults |

Describe every field with `Field(description=...)`: it is shown on hover in the forms (see the
[integration guide](pybiscus_model_guide.md)).

# Multi projects mode : developping plugins in separated projects

__The following guidelines, extracted from the _cypia_ plugin project, demonstrate how to structure your development environment so that the Pybiscus core and each plugin are maintained in their own dedicated project.__

This project is a suite of plugins for the Pybiscus federated learning framework:
https://github.com/ThalesGroup/pybiscus
which is itself based on the flower framework:
https://github.com/adap/flower

The intention is to enable a clear separation between the pybiscus core
and its plugins, in order to be able to use external code
without impacting the pybiscus core, particularly to have isolation
between pybiscus dependencies and those of its plugins.

This relies on the use of the uv tool (from Astral)

uv is an ultra-fast Python dependency and environment management tool, compatible with pyproject.toml standards, which replaces pip, pip-tools, virtualenv and setuptools install all at once.

We use the workspace concept for this,
which allows to logically group several projects and
produce a workspace virtual environment that is the fusion of the workspace projects.

## General organization

A workspace directory, in which we will clone the two repositories side by side:

```bash
mkdir workspace
cd workspace
git clone https://github.com/ThalesGroup/pybiscus
git clone https://my-plugin-repository-url/cypia
```

```
workspace/
├── pyproject.toml
├── pybiscus/
├── cypia/
```

## The cypia project structure

```
cypia/
├── .python.version
├── pyproject.toml
├── pybiscus.env
├── cypia-plugins-conf.yml
├── cypia/
│   └── __init__.py
├── workspace/
│   ├── init.sh
│   └── pyproject.toml
```

## The cypia project's pyproject.toml

The project has a dependency on the parent pybiscus project,
in addition to its own dependencies,
as well as an indication that it is part of a workspace:

```

dependencies = [
  "plugin-deps>=1.5.0",
  ...
  "pybiscus",
]

...

[tool.uv.sources]
pybiscus = { workspace = true }

```

## The pybiscus + cypia workspace pyproject.toml

The workspace/init shell must allow initializing the workspace

it copies the pyproject.toml file:

```
[tool.uv.workspace]
members = ["pybiscus", "cypia"]
```

```bash
#!/usr/bin/bash

cp pyproject.toml ..
cd ..
uv sync
```

## Plugin configuration

To specify the definition of the plugins used, you can configure the plugin configuration file (default file: **pybiscus-plugins-conf.yml**, but configurable via the **PYBISCUS_PLUGIN_CONF_PATH** environment variable) by overriding this variable in the **pybiscus.env** file with these 2 possibilities:

- override the plugin configuration file in order to use only the project plugins :

```
PYBISCUS_PLUGIN_CONF_PATH="./cypia-plugins-conf.yml"
```
- merge several plugin configuration files in order to use both the project plugins and the pybiscus ones :

```
PYBISCUS_PLUGIN_CONF_PATH="../pybiscus/pybiscus-plugins-conf.yml:./cypia-plugins-conf.yml"
```

## How to develop / execute

Once the workspace has been inited by executing the  workspace/init shell.

By positionning in the cypia directory,
we can access to pybiscus python packages,
and pybiscus shells can be ran using their relative path 
( by example: ../pybiscus/launch/agent/cli/5000.sh )
