import inspect
from pathlib import Path
from typing import Any, ClassVar

import typer
from lightning.pytorch import Trainer
from lightning.pytorch.callbacks import RichModelSummary, RichProgressBar
from lightning.pytorch.callbacks.progress.rich_progress import RichProgressBarTheme
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Annotated

from pybiscus.plugin.registries.data_registry import DataConfig, datamodule_registry
from pybiscus.plugin.registries.model_registry import ModelConfig, model_registry

from pybiscus.commands.apps_common import exit_on_invalid_config, load_config, resolve_defaults


class ConfigLocalTrain(BaseModel):
    """a model trained on one site's data, without federation: a baseline for the federated runs"""

    PYBISCUS_ALIAS: ClassVar[str] = "Pybiscus local training configuration"

    root_dir: str = Field(default="${oc.env:PWD}", description="directory the data and the experiments are relative to")
    trainer: dict[str, Any] = Field(default_factory=dict, description=
        "keyword arguments of Lightning's Trainer (max_epochs, accelerator, devices...)")
    data: DataConfig()  # pyright: ignore[reportInvalidTypeForm]
    model: ModelConfig()  # pyright: ignore[reportInvalidTypeForm]

    model_config = ConfigDict(extra="forbid")

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
    try:
        conf = resolve_defaults(ConfigLocalTrain, ConfigLocalTrain(**conf_loaded))
    except ValidationError as e:
        exit_on_invalid_config(e)

    model_class = model_registry()[conf.model.name]
    model_kwargs = conf.model.config.model_dump()
    # only some models log to Lightning (self.log); the others take no such argument
    if "_logging" in inspect.signature(model_class.__init__).parameters:
        model_kwargs["_logging"] = True
    model = model_class(**model_kwargs)
    data = datamodule_registry()[conf.data.name](**conf.data.config.model_dump())

    trainer = Trainer(
        default_root_dir=Path(conf.root_dir) / "experiments/local/",
        enable_checkpointing=True,
        logger=True,
        # max_epochs=conf_loaded["epochs"],
        callbacks=[
            RichModelSummary(),
            RichProgressBar(theme=RichProgressBarTheme(metrics="blue")),
        ],
        **conf.trainer,
    )

    trainer.fit(model, data)
    with open(trainer.log_dir + "/config_launch.yml", "w") as file:
        OmegaConf.save(config=conf_loaded, f=file)


if __name__ == "__main__":
    app()
