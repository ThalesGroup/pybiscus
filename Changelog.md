# Changelog

## [Unreleased]

* moving loops_fabric.py into ml directory (a better place)
* getting rid of load_data_paroma, amd replaces it by direct use of LightningDataModule.
* updating config files accordingly
* moving logging of evaluate function to evaluate inside FabricStrategy; more coherence with aggregate_fit and aggregate_evaulate.
* upgrading the config for local training with key 'trainer', making all Trainer arguments virtually available 
* adding a constraint on deepspeed library due to some issues with the installation of the wheel. Issue with poetry? In poetry, version is 0.9.0 but in installing the wheel built by poetry, it is 0.11.1...