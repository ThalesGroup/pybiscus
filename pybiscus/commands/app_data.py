from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import typer
from omegaconf import OmegaConf
from pydantic import TypeAdapter, ValidationError

import pybiscus.core.pybiscus_logger as logm
from pybiscus.commands.apps_common import exit_on_invalid_config, load_config
from pybiscus.ml.datasplit import labels_of, split_indices

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")


@app.callback()
def data():
    """The data part of Pybiscus.

    * The command partition shows how train.partition splits the training data between the
      clients, and can export each client's example indices.
    """


def write_indices(path: Path, indices: np.ndarray) -> None:
    # one index per line: the format of PR #44's files, read back by train.indices / val.indices
    path.write_text("".join(f"{i}\n" for i in indices.tolist()), encoding="utf-8")


@app.command(name="partition")
def partition(
    config: Annotated[Path, typer.Argument(help="a client configuration whose data section has train.partition")],
    export: Annotated[Optional[Path], typer.Option(help="directory where client_<i>_train.txt / client_<i>_val.txt are written")] = None,
) -> None:
    """Show the share of every client of train.partition, and optionally export their indices.

    The partition is computed from the data section of the configuration, for every partition_id:
    the files list, for each client, the indices of its training and (holdout) validation examples
    in the official train split. They can be used as train.indices / val.indices, or to know which
    examples trained which client (membership inference analysis).
    """

    from pybiscus.plugin.registries.data_registry import DataConfig, datamodule_registry

    conf_loaded = load_config(config)
    data_section = OmegaConf.to_container(conf_loaded, resolve=True).get("data")
    if data_section is None:
        logm.console.log("❌ the configuration has no data section")
        raise typer.Exit(code=2)
    try:
        conf = TypeAdapter(DataConfig()).validate_python(data_section)
    except ValidationError as e:
        exit_on_invalid_config(e)

    datamodule = datamodule_registry()[conf.name](**conf.config.model_dump())
    if not hasattr(datamodule, "train_source") or not hasattr(conf.config, "train"):
        logm.console.log(f"❌ the data plugin {conf.name} does not support partitions (no train section / train_source())")
        raise typer.Exit(code=2)
    train, val = conf.config.train, conf.config.val
    if train.partition is None:
        logm.console.log("❌ the data section has no train.partition")
        raise typer.Exit(code=2)

    train_full = datamodule.train_source()
    try:
        labels = labels_of(train_full)
    except ValueError:
        labels = None
    if export is not None:
        export.mkdir(parents=True, exist_ok=True)

    p = train.partition
    unit = "units" if hasattr(datamodule, "split_units") else "examples"
    logm.console.log(f"{p.scheme.value} partition of {len(train_full)} {unit} between {p.num_partitions} clients (seed {p.seed})")
    for i in range(p.num_partitions):
        share = p.model_copy(update={"partition_id": i})
        # a plugin whose units are not the examples (hdfs: whole sequences) splits them itself
        if hasattr(datamodule, "split_units"):
            train_idx, val_idx = datamodule.split_units(share)
        else:
            train_idx, val_idx = split_indices(train_full, train.model_copy(update={"partition": share}), val)
        line = f"client {i}: {len(train_idx)} training {unit}"
        if val_idx is not None:
            line += f", {len(val_idx)} validation {unit}"
        if labels is not None:
            counts = np.bincount(labels[train_idx])
            line += f" | classes present (> 2 %): {int((counts / len(train_idx) > 0.02).sum())}, main class {counts.max() / len(train_idx):.0%}"
        logm.console.log(line)
        if export is not None:
            write_indices(export / f"client_{i}_train.txt", train_idx)
            if val_idx is not None:
                write_indices(export / f"client_{i}_val.txt", val_idx)
    if export is not None:
        logm.console.log(f"indices written in {export}")
