from pathlib import Path
from typing import Annotated

import typer
from lightning.pytorch import Trainer
from lightning.pytorch.callbacks import RichModelSummary, RichProgressBar
from lightning.pytorch.callbacks.progress.rich_progress import RichProgressBarTheme
from omegaconf import OmegaConf

from src.console import console
from src.ml.registry import datamodule_registry, model_registry

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")


@app.callback()
def local():
    """The local part of Pybiscus.

    Train locally the model.
    """


@app.command()
def train_config(config: Annotated[Path, typer.Argument()] = None):
    """Launch a local training.

    This function is here mostly for prototyping and testing models on local data, without the burden of potential Federated Learning issues.
    It is simply a re implementation of the Lightning CLI, adapted for Pybiscus.

    Parameters
    ----------
    config : Path
        the path to the configuration file.

    Raises
    ------
    typer.Abort
        _description_
    typer.Abort
        _description_
    typer.Abort
        _description_
    """
    if config is None:
        print("No config file")
        raise typer.Abort()
    if config.is_file():
        conf = OmegaConf.load(config)
        console.log(dict(conf))
    elif config.is_dir():
        print("Config is a directory, will use all its config files")
        raise typer.Abort()
    elif not config.exists():
        print("The config doesn't exist")
        raise typer.Abort()

    model = model_registry[conf["model"]["name"]](
        **conf["model"]["config"], _logging=True
    )
    data = datamodule_registry[conf["data"]["name"]](**conf["data"]["config"])

    trainer = Trainer(
        default_root_dir=Path(conf["root_dir"]) / "experiments/local/",
        enable_checkpointing=True,
        logger=True,
        # max_epochs=conf["epochs"],
        callbacks=[
            RichModelSummary(),
            RichProgressBar(theme=RichProgressBarTheme(metrics="blue")),
        ],
        **conf["trainer"],
    )

    trainer.fit(model, data)
    with open(trainer.log_dir + "/config_launch.yml", "w") as file:
        OmegaConf.save(config=conf, f=file)


if __name__ == "__main__":
    app()
