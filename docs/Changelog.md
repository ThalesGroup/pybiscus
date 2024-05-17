# Changelog

## TODO

* Remove tests, or find a way to test the jsonargparse CLI.
* Adapt github workflow to Rye ; remove/change the test workflow ; remove the publish part.
* Improve the CLI: how to transform a simple function (launch_client for instance) into a CLI, without duplication of code?
* Think about the necessity of Pydantic validation.
* Refacto of container part.
* Improve and change the documentation.

## [Version 0.7.0.dev0]

* **Bump Typer CLI to jsonargparse**. Typer CLI was great to build Pybiscus as a PoC, but it has some limitations: really slow, it does not support configuration files through the arguments of the CLI, you need to rewrite the Pydantic models into the arguments of the CLI... One issue in particular was the difficulty of writing nested configuration directly in the CLI, which is important if you want to easily override parameters in the config file.
* Remove: helper functions to check the config. Not needed with jsonargparse
* Add: a toplevel layer 'config_server' or 'config_client' at the top of the configuration files.

## [Version 0.6.1]

* Fix: Pydantic version, unfortunately pinned to non existing version 2.6.
* Improve: documentation, still a work in progress.

## [Version 0.6.0.dev0]

* **BREAKING CHANGE** Renaming 'src' directory into 'pybiscus' to follow the structure expected by Poetry to properly build the package. First step towards packaging the tool.
* **REFACTO** The "FabricStrategy" approach is now deprecated. Instead, a few callbacks, based on Fabric and Rich, allows to easily "upgrade" the usual weighted average and evaluation functions, for generic Strategies. Note that for now, only the classical FedAvg Strategy provided by Flower has been tested.
* Starting a small test suite. For now, only test the 'check' parts of client and server applications, on different config files to test good/bad returns.
* Correcting a bug on the weighted_average function: "is set()" had to be replaced by "==set()". Metrics are now aggregated and averaged.
* Introducing a short helper function to merge the configuration from the config file passed as an argument of server or client, and the optional arguments, if passed.


## [Version 0.5.0]

* Renaming the commands of client and server parts. Improving the help printed by Typer.
* Adding a new check command for both Server and Client sides in order to possibly check before-hand the validity of the provided configuration file.
* **REFACTO**: the main commands of the pybiscus app are now located in src/commands. For instance, the previous version of `src/flower/client_fabric.py` is split into the Typer part src/commands/app_client.py and the new version of `src/flower/client_fabric.py`. This helps structure the code into more distinct block.
* The Unet3D Module comes now with a better Dice Loss and a Dice metric instead of the Accuracy (not suitable in the context of segmentation of 3D images).
* Small change on the `weighted_average` function, to take care of the change of keywords.
* **NEW FEATURE**: using Trogon to add a Terminal User Interface command to the Pybiscus app. This helps new users to browse through help, existing commands and their syntax.

## [Version 0.4.0]

* the Server has now the possibility to save the weights of the model at the end of the FL session.
* add the possibility to perform a pre train validation loop on the Client. This feature allows to perform one validation loop, on the validation dataset holds by the client, of the newly sent, aggregated weights.
* updating the Lightning version needed: not "all" anymore, just "pytorch-extra" in order to have way less dependencies to install and check.

* **NEW FEATURE**: using Pydantic to validate ahead of time the configuration given to the CLI:
    - data config validation
    - model config validaton
    - server config validation
    - client config validation
    - Fabric config validation
    - Streategy config validation
* adding some documentation for the use of config files.
* updating the documentation on various classes and functions.

## [Version 0.3.3]

* moving loops_fabric.py into ml directory (a better place)
* getting rid of load_data_paroma, amd replaces it by direct use of LightningDataModule.
* updating config files accordingly
* moving logging of evaluate function to evaluate inside FabricStrategy; more coherence with aggregate_fit and aggregate_evaulate.
* upgrading the config for local training with key 'trainer', making all Trainer arguments virtually available
* adding a constraint on deepspeed library due to some issues with the installation of the wheel. Issue with poetry? In poetry, version is 0.9.0 but in installing the wheel built by poetry, it is 0.11.1...
