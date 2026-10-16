import importlib
import inspect
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Optional, Union, get_args, get_origin

import typer
import yaml
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

import pybiscus.core.pybiscus_logger as logm
from pybiscus.pydantic2xxx.heredoc import get_basemodel_attribute_description

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")

REFERENCE = Path("docs/plugins-reference.md")

# family, registry module, its accessors, the configuration keys a family's blocks are found under, what it is for
FAMILIES = [
    ("Data", "data_registry", "datamodule_registry", "DataConfig", ("data",),
     "a dataset and how it is split into train, validation and test sections (`data:` of the server and of the clients)"),
    ("Models", "model_registry", "model_registry", "ModelConfig", ("model",),
     "the model trained by the clients and evaluated by the server (`model:`); the server and the clients must name the same one"),
    ("Strategies", "strategy_registry", "strategy_registry", "StrategyConfig", ("strategy",),
     "how the server aggregates the clients' updates (`server_strategy.strategy`)"),
    ("Strategy decorators", "strategydecorator_registry", "strategydecorator_registry", "StrategyDecoratorConfig", ("pipeline",),
     "steps around the strategy, in the order of `server_strategy.pipeline`: metrics, saving, privacy, robustness"),
    ("Clients", "client_registry", "client_registry", "ClientConfig", ("alternate_client_class",),
     "a client that replaces the ordinary one (`flower_client.alternate_client_class`)"),
    ("Loggers", "logger_registry", "logger_registry", "LoggerConfig", ("loggers",),
     "where the server's log lines go (`server_run.loggers`)"),
    ("Metrics loggers", "metriclogger_registry", "metricslogger_registry", "MetricsLoggerConfig", ("metrics_loggers",),
     "where the metrics go (`server_compute_context.metrics_loggers`)"),
    ("Result modifiers", "resultmodifier_registry", "resultmodifier_registry", "ResultModifierConfig", ("result_modifier",),
     "a change made to a client's result before aggregation (the `result_modifier` of `personalizeclientsfitin`)"),
    ("Stopping criteria", "stoppingcriterion_registry", "stoppingcriterion_registry", "StoppingCriterionConfig", ("stopping",),
     "when the server ends the session before its `num_rounds`, tested after each round (`server_run.stopping`)"),
    ("Fit results aggregators", "flowerfitresultagregator_registry", "flowerfitresultsaggregator_registry",
     "FlowerFitResultsAggregatorConfig", ("aggregator",),
     "how the clients' fit metrics are combined (the `aggregator` of `fedavgwithaggregator`)"),
]

# a docstring copied from Lightning's own examples says nothing of the plugin
BOILERPLATE = ("A LightningDataModule is an abstract class", "A LightningModule is an abstract class",
               "Pydantic BaseModel to validate", "Pydantic Model used to validate", "A Pydantic Model to validate",
               "Pydantic model to validate", "A Pydantic model")

# sections shared by many plugins, described once: a plugin's table refers to the page instead of
# repeating their fields (the data sections of every dataset)
SHARED_SECTIONS = {"pybiscus.ml.datasplit": "configuration.md#data"}


@app.callback()
def plugins():
    """The plugins Pybiscus loads.

    * The command doc writes the reference of every loaded plugin: its configuration fields,
      defaults and descriptions, and the shipped configurations that use it.
    """


def type_name(annotation) -> str:
    origin = get_origin(annotation)
    if origin is Annotated:
        return type_name(get_args(annotation)[0])
    if origin is Literal:
        return " \\| ".join(repr(v) for v in get_args(annotation))
    if origin is Union or str(origin) == "types.UnionType":
        args = [a for a in get_args(annotation) if a is not type(None)]
        names = " \\| ".join(type_name(a) for a in args)
        return f"{names} (optional)" if len(args) < len(get_args(annotation)) else names
    if origin in (list, tuple, set, dict):
        return f"{origin.__name__}[{', '.join(type_name(a) for a in get_args(annotation))}]"
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return " \\| ".join(repr(m.value) for m in annotation)
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        name = getattr(annotation.model_fields.get("name"), "annotation", None)
        return f"`{get_args(name)[0]}`" if get_origin(name) is Literal else "section"
    return getattr(annotation, "__name__", str(annotation)).replace("|", "\\|")


def section_of(annotation):
    """the model of a nested section, its fields being listed under it; none for a plugin's union"""
    args = [a for a in get_args(annotation) if a is not type(None)] if get_origin(annotation) in (Union,) else [annotation]
    if len(args) == 1 and inspect.isclass(args[0]) and issubclass(args[0], BaseModel) and "name" not in args[0].model_fields:
        return args[0]
    return None


def cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def field_rows(model, prefix=""):
    for name, field in model.model_fields.items():
        if field.exclude:
            continue
        description = field.description or get_basemodel_attribute_description(model, name) or ""
        if field.default is not PydanticUndefined:
            value = field.default.value if isinstance(field.default, Enum) else field.default
            default = f"`{value!r}`" if not isinstance(value, BaseModel) else "(section)"
        else:
            default = "(computed)" if field.default_factory else "required"
        sub = section_of(field.annotation)
        shared = SHARED_SECTIONS.get(sub.__module__) if sub else None
        kind = f"section, see [{shared.split('#')[0]}]({shared})" if shared else "section" if sub else type_name(field.annotation)
        yield f"| `{prefix}{name}` | {kind} | {default} | {cell(description)} |"
        if sub and not shared:
            yield from field_rows(sub, f"{prefix}{name}.")


def first_paragraph(*classes) -> str:
    for cls in classes:
        doc = inspect.cleandoc(cls.__dict__.get("__doc__") or "") if cls else ""
        if not doc or doc.startswith(BOILERPLATE) or re.match(r"^\w+\s*:\s*[\w\[\], .]+?\s*(=|$)", doc.split("\n")[0]):
            continue
        return " ".join(doc.split("\n\n")[0].split())
    return ""


def where_used(configs_dir: Path):
    """for each configuration key of a family, the names its blocks give, and the files they are in"""
    used = {}

    def walk(node, key, path):
        if isinstance(node, dict):
            if key and "name" in node and isinstance(node["name"], str):
                used.setdefault((key, node["name"]), set()).add(path)
            for k, v in node.items():
                walk(v, k, path)
        elif isinstance(node, list):
            for item in node:
                walk(item, key, path)

    for path in sorted(configs_dir.rglob("*.yml")):
        if "uploaded" in path.parts:
            continue
        try:
            walk(yaml.safe_load(path.read_text(encoding="utf-8")), None, path.as_posix())
        except yaml.YAMLError:
            continue
    return used


def plugin_place(cls) -> str:
    module = sys.modules.get(cls.__module__)
    file = Path(getattr(module, "__file__", "") or "")
    try:
        relative = file.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return f"`{cls.__module__}`"
    return f"`{relative.parent.as_posix()}`"


def reference() -> str:
    used = where_used(Path("configs"))
    lines = ["# Plugins reference", "",
             "<!-- generated by `pybiscus plugins doc`: edit the plugins' docstrings and field descriptions, not this file -->",
             "",
             "Every plugin Pybiscus loads from the bundled manifests (`pybiscus-plugins/plugins-conf.yml` and",
             "`pybiscus-plugins-hierarchical/plugins-conf.yml`), family by family: the `name:` a configuration gives it,",
             "where it comes from, what it does, its configuration fields, and the shipped configurations of `configs/`",
             "that use it. How to write one: [Plugins](plugins.md), [How-to](how-to.md). The privacy evaluation of",
             "PR #44 (`pybiscus-plugins-privacy-evaluation/`, not finalized) is not described here: see",
             "[privacy-evaluation.md](privacy-evaluation.md).", ""]
    body, toc = [], []
    for title, module, registry_name, config_name, keys, purpose in FAMILIES:
        registries = importlib.import_module(f"pybiscus.plugin.registries.{module}")
        registry, union = getattr(registries, registry_name)(), getattr(registries, config_name)()
        if union is None:
            continue
        members = get_args(union)[0]
        # a union of one member is that member
        members = get_args(members) if get_origin(members) is Union else (members,)
        anchor = title.lower().replace(" ", "-")
        toc.append(f"- [{title}](#{anchor}): " + ", ".join(f"`{get_args(m.model_fields['name'].annotation)[0]}`" for m in members))
        body += [f"## {title}", "", f"{purpose[0].upper()}{purpose[1:]}.", ""]
        for config in members:
            name = get_args(config.model_fields["name"].annotation)[0]
            implementation = registry.get(name)
            inner = section_of(config.model_fields["config"].annotation) if "config" in config.model_fields else None
            alias = getattr(config, "PYBISCUS_ALIAS", None)
            origin = getattr(config, "PYBISCUS_MODULE_ORIGIN", "?")
            body += [f"### `{name}`" + (f" — {alias}" if alias and alias != name else ""), ""]
            body += [f"*{'core' if origin == 'core' else 'plugin'}, {plugin_place(implementation) if implementation else '?'}*", ""]
            description = first_paragraph(implementation, inner, config)
            if description:
                body += [description, ""]
            if inner and set(inner.model_fields) == {"empty_configuration"}:
                # the placeholder field of a plugin without settings
                body += ["No configuration (`config: {empty_configuration: true}`).", ""]
            elif inner and inner.model_fields:
                body += ["| field (under `config`) | type | default | description |", "|---|---|---|---|", *field_rows(inner), ""]
            elif inner is not None:
                body += ["No configuration (`config: {}`).", ""]
            files = sorted(set().union(*(used.get((key, name), set()) for key in keys)))
            if files:
                body += ["Used by: " + ", ".join(f"[`{f}`](../{f})" for f in files), ""]
    return "\n".join(lines + toc + [""] + body).rstrip() + "\n"


@app.command(name="doc")
def doc(
    output: Annotated[Path, typer.Option(help="the reference file")] = REFERENCE,
    check: Annotated[bool, typer.Option(help="only compare: exit 1 when the file differs from what the plugins give")] = False,
) -> None:
    """Write the reference of the loaded plugins (run from the repository root, with the hierarchical
    plugins' manifest: PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml)."""
    text = reference()
    if check:
        current = output.read_text(encoding="utf-8") if output.is_file() else ""
        if current != text:
            logm.console.log(f"❌ {output} is not up to date: run pybiscus plugins doc")
            raise typer.Exit(1)
        logm.console.log(f"✅ {output} is up to date")
        return
    output.write_text(text, encoding="utf-8")
    logm.console.log(f"📚 {output} written")
