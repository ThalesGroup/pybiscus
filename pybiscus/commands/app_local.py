from pathlib import Path

import typer
from lightning.pytorch import Trainer
from lightning.pytorch.callbacks import RichModelSummary, RichProgressBar
from lightning.pytorch.callbacks.progress.rich_progress import RichProgressBarTheme
from omegaconf import OmegaConf
from typing import Annotated

from pybiscus.plugin.registries import datamodule_registry, model_registry

from pybiscus.commands.apps_common import load_config

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

    # handling mandatory config path parameter

    conf_loaded = load_config(config)

    model = model_registry()[conf_loaded["model"]["name"]](
        **conf_loaded["model"]["config"], _logging=True
    )
    data = datamodule_registry()[conf_loaded["data"]["name"]](**conf_loaded["data"]["config"])

    trainer = Trainer(
        default_root_dir=Path(conf_loaded["server_run"]["root_dir"]) / "experiments/local/",
        enable_checkpointing=True,
        logger=True,
        # max_epochs=conf_loaded["epochs"],
        callbacks=[
            RichModelSummary(),
            RichProgressBar(theme=RichProgressBarTheme(metrics="blue")),
        ],
        **conf_loaded["trainer"],
    )

    trainer.fit(model, data)
    with open(trainer.log_dir + "/config_launch.yml", "w") as file:
        OmegaConf.save(config=conf_loaded, f=file)


if __name__ == "__main__":
    app()
