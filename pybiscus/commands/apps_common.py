import pybiscus.core.pybiscus_logger as logm
import os
import typer
from pathlib import Path
from omegaconf import DictConfig, ListConfig, OmegaConf
from typing import NoReturn, Optional, Union
from dotenv import load_dotenv
from pydantic import ValidationError

# the agent tells an invalid config from a crash by this exit code, not by parsing the output
# (65 = EX_DATAERR ; typer already uses 2 for usage errors)
CONFIG_VALIDATION_EXIT_CODE = 65
# plugin manifest or plugin import failure (78 = EX_CONFIG)
PLUGIN_ERROR_EXIT_CODE = 78


def exit_on_invalid_config(error: ValidationError) -> NoReturn:
    from pybiscus.plugin.pluginmanager import get_skipped_plugins

    message = f"This is not a valid config!\n{error}"
    # a config naming a skipped plugin only gets "tag '...' does not match": give the cause
    skipped = get_skipped_plugins()
    if skipped:
        message += "\nSkipped plugins (missing dependency): " + ", ".join(
            f"{category}/{module} (needs '{dependency}')" for category, module, dependency in skipped
        )
    logm.console.log(message)
    raise typer.Exit(code=CONFIG_VALIDATION_EXIT_CODE)


def resolve_defaults(model_class, conf):
    """conf validated again with the interpolations of its defaults resolved"""
    dumped = conf.model_dump(mode="json")
    # OmegaConf resolves the YAML, then Pydantic adds the defaults: one holding an interpolation
    # (reporting.basedir = "${root_dir}/experiments", the data plugins' dir) stayed a literal
    # string, and a directory named "${root_dir}" appeared
    if "${" not in str(dumped):
        return conf
    return model_class(**OmegaConf.to_container(OmegaConf.create(dumped), resolve=True))


def load_config( config: Path ) -> DictConfig:

    if config is None:
        logm.interactiveConsole.log("No config file")
        raise typer.Abort()
    if config.is_file():
        conf_loaded = OmegaConf.load(config)
        # logm.interactiveConsole.log(conf)
    elif config.is_dir():
        logm.interactiveConsole.log("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        logm.interactiveConsole.log("The config doesn't exist")
        raise typer.Abort()

    return conf_loaded


def _plugins_detail(message: str) -> None:
    from pybiscus.plugin.pluginmanager import plugins_verbose
    if plugins_verbose():
        logm.interactiveConsole.log(message)


def load_config_with_env(env_var: str, default: str) -> DictConfig:
    """
    Load configuration from multiple files specified in environment variable.
    Resolves relative paths based on each config file's directory.
    """
    load_dotenv(dotenv_path="pybiscus.env", override=False)

    # 1. Read environment variable and parse config file paths
    raw_value = os.getenv(env_var, default)
    separator = ':'  # Could add Windows support: ';' if os.name == 'nt' else ':'
    config_files = [Path(p.strip()).resolve() for p in raw_value.split(separator) if p.strip()]

    logm.interactiveConsole.log(f"🔍 [plugins] Using config files (resolved): {config_files}")

    # 2. Load and post-process each file
    def load_and_resolve_config(conf_path: Path) -> DictConfig:
        """Load a config file and resolve relative paths within it."""
        _plugins_detail(f"🔍 [plugins] Loading config: {conf_path}")
        
        # Ensure the config file exists
        if not conf_path.exists():
            raise FileNotFoundError(f"Config file not found: {conf_path}")
            
        conf = OmegaConf.load(conf_path)
        base_path = conf_path.parent

        def resolve_paths(obj: Union[DictConfig, ListConfig, list, str, any], current_base: Path):
            """Recursively resolve relative paths in the configuration."""
            
            if isinstance(obj, DictConfig):
                # Handle dictionary-like objects
                for key, val in obj.items():
                    if key == "path" and isinstance(val, str):
                        # Resolve path if it's relative
                        original_path = Path(val)
                        if not original_path.is_absolute():
                            # Handle ~ expansion first, then resolve relative to config file
                            if val.startswith("~/"):
                                resolved_path = Path(val).expanduser().resolve()
                            else:
                                resolved_path = (current_base / original_path).resolve()
                            obj[key] = str(resolved_path)
                            _plugins_detail(f"🔍 [plugins] Resolved path: {val} => {obj[key]}")
                    else:
                        # Recursively process nested structures
                        resolve_paths(val, current_base)
                        
            elif isinstance(obj, (list, ListConfig)):
                # Handle lists and ListConfig - iterate through each item
                for item in obj:
                    resolve_paths(item, current_base)

        resolve_paths(conf, base_path)
        return conf

    # 3. Load all configurations and merge them
    try:
        resolved_confs = [load_and_resolve_config(path) for path in config_files]
        
        # Custom merge strategy to concatenate lists instead of replacing them
        if len(resolved_confs) == 1:
            merged_config = resolved_confs[0]
        else:
            # Start with the first config
            merged_config = resolved_confs[0]
            
            # Merge each subsequent config
            for conf in resolved_confs[1:]:
                for key, value in conf.items():
                    if key in merged_config:
                        # If both have the same key and both are lists, concatenate them
                        if isinstance(merged_config[key], (list, ListConfig)) and isinstance(value, (list, ListConfig)):
                            # Convert to regular lists, concatenate, then back to ListConfig
                            merged_list = list(merged_config[key]) + list(value)
                            merged_config[key] = OmegaConf.create(merged_list)
                            _plugins_detail(f"🔍 [plugins] Merged lists for key '{key}': {len(merged_config[key])} total items")
                        else:
                            # For non-lists, use OmegaConf merge (replace behavior)
                            merged_config[key] = value
                            _plugins_detail(f"🔍 [plugins] Replaced key '{key}' with new value")
                    else:
                        # Key doesn't exist in merged config, just add it
                        merged_config[key] = value
                        _plugins_detail(f"🔍 [plugins] Added new key '{key}'")
        
        logm.interactiveConsole.log(f"✅ [plugins] Successfully loaded and merged {len(config_files)} config files")
        return merged_config
        
    except Exception as e:
        logm.interactiveConsole.log(f"❌ [plugins] Error loading configuration: {e}")
        raise


# Example usage and testing
if __name__ == "__main__":
    # Example: Load config from environment variable
    try:
        config = load_config_with_env("PLUGIN_CONFIG_PATHS", "default_config.yaml")
        logm.interactiveConsole.log("Final config structure:")
        logm.interactiveConsole.log(OmegaConf.to_yaml(config))
    except Exception as e:
        logm.interactiveConsole.log(f"Failed to load config: {e}")


def apply_num_threads(num_threads: Optional[int]) -> None:
    # PyTorch takes every physical core in each process: several clients on one machine then run
    # far more threads than cores, which wait for each other at every parallel operation (the
    # round of three cifar10 clients that never ended)
    if num_threads is not None:
        import torch
        torch.set_num_threads(num_threads)
        logm.console.log(f"🧵 PyTorch limited to {num_threads} CPU threads")


def apply_seed(seed: Optional[int]) -> None:
    if seed is not None:
        from lightning.fabric.utilities.seed import seed_everything
        # verbose=False: Lightning's own message bypasses the logger multiplexed to the GUI
        seed_everything(seed, verbose=False)
        logm.console.log(f"🎲 random generators seeded with {seed}")
