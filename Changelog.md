# Changelog

## [Unreleased]

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