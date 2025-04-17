import typer

from pathlib import Path
from omegaconf import OmegaConf, DictConfig

def load_config( config: Path ) -> DictConfig:

    if config is None:
        print("No config file")
        raise typer.Abort()
    if config.is_file():
        conf_loaded = OmegaConf.load(config)
        # console.log(conf)
    elif config.is_dir():
        print("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        print("The config doesn't exist")
        raise typer.Abort()

    return conf_loaded
