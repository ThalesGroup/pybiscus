"""The session's presets (options_set, values_set) applied to a configuration in Python, as the agent's
form applies them in the browser: an agent launched by an order has no form."""

import copy
import json
from typing import Annotated, Optional, Union, get_args, get_origin

from pydantic import BaseModel, TypeAdapter

from pybiscus.pydantic2xxx.pydantic2html import generate_tab_name, option_name
from pybiscus.session.interpolation import calls_resolver

# the form's names of an Optional's tabs: ' ' holds a value, '  ' is None
SOME, NONE = " ", "  "

# the items an empty list starts with, by their option's label: the form adds them (lists_management.js),
# and so does an agent launched by order from the defaults
LIST_DEFAULTS = {
    "server_run.loggers": ["WebHook"],
    "server_compute_context.metrics_loggers": ["WebHook"],
    "server_strategy.pipeline": ["MetricDiffCompute", "TimeDiffCompute", "VisualizeModelLayers"],
}


def list_defaults_js() -> str:
    return f"const PYBISCUS_LIST_DEFAULTS = {json.dumps(LIST_DEFAULTS)};\n"


def accepted(presets: dict) -> tuple[dict, list, dict, list, list]:
    """options_set, options_lock, values_set, values_lock, and the names ignored: a value calling an
    interpolation resolver (${oc.env:…}) would read this machine"""
    ignored = [name for name, value in {**presets.get("options_set", {}), **presets.get("values_set", {})}.items()
               if calls_resolver(value)]
    return ({k: v for k, v in presets.get("options_set", {}).items() if k not in ignored},
            [k for k in presets.get("options_lock", []) if k not in ignored],
            {k: v for k, v in presets.get("values_set", {}).items() if k not in ignored},
            [k for k in presets.get("values_lock", []) if k not in ignored],
            ignored)


def as_text(value) -> str:
    # the form reads every value as text. A Python bool became 'True', which the form's JSON.parse
    # refuses: the exception left every value after it unset and every lock undone
    return str(value).lower() if isinstance(value, bool) else str(value)


def _strip(tp):
    while get_origin(tp) is Annotated:
        tp = get_args(tp)[0]
    return tp


def _is_optional(tp) -> bool:
    tp = _strip(tp)
    return get_origin(tp) is Union and type(None) in get_args(tp)


def _members(tp) -> list:
    tp = _strip(tp)
    if get_origin(tp) is Union:
        # Optional[Annotated[Union[...]]] (a client's data): the plugins' union nested in the Optional
        return [member for arg in get_args(tp) if arg is not type(None) for member in _members(arg)]
    return [tp]


def _is_model(tp) -> bool:
    return isinstance(tp, type) and issubclass(tp, BaseModel)


def _model_of(declared, value) -> Optional[type]:
    """the union's member a dict holds: by its `name`, the unions' discriminator"""
    models = [m for m in _members(declared) if _is_model(m)]
    if len(models) == 1:
        return models[0]
    if isinstance(value, dict):
        for model in models:
            if option_name(model) == value.get("name"):
                return model
    return None


def fresh(model) -> dict:
    """an option newly selected, as its tab shows it: its required sections too (a data's config,
    whose fields all have defaults, has none itself), with their first option"""
    sections = {"name": option_name(model)} if option_name(model) else {}
    for key, field in model.model_fields.items():
        # an Optional without a default opens set in the form (a client's data), as a required section
        if key == "name" or not field.is_required():
            continue
        models = [m for m in _members(field.annotation) if _is_model(m)]
        if models:
            sections[key] = fresh(models[0])
    return sections


def defaults(model) -> dict:
    """the configuration the form shows before any preset: the first option of each union, the required
    sections, the lists' default items (an option a plugin not loaded brings is left out, as the form does)"""
    config = fresh(model)
    for prefix, labels in LIST_DEFAULTS.items():
        keys = prefix.split(".")
        located = _parent(model, config, keys)
        if located is None:
            continue
        declared, node = located
        holder = _model_of(declared, node)
        if holder is None or keys[-1] not in holder.model_fields or node.get(keys[-1]):
            continue
        elements = [get_args(m)[0] for m in _members(holder.model_fields[keys[-1]].annotation) if get_origin(m) is list]
        options = {generate_tab_name(m, ""): m for e in elements for m in _members(e) if _is_model(m)}
        node[keys[-1]] = [fresh(options[label]) for label in labels if label in options]
    return config


def complete(declared, node) -> None:
    """every field the configuration leaves out, with its default, as the form writes them all: the
    check resolves the interpolations (${root_dir}/...) before Pydantic adds the defaults, and one
    naming a key absent from the file fails"""
    if isinstance(node, list):
        elements = [get_args(m)[0] for m in _members(declared) if get_origin(m) is list and get_args(m)]
        for item in node:
            if elements:
                complete(elements[0], item)
        return
    if not isinstance(node, dict):
        return
    model = _model_of(declared, node)
    if model is None:
        return
    for key, field in model.model_fields.items():
        if key not in node and not field.is_required():
            default = field.get_default(call_default_factory=True)
            node[key] = None if default is None else TypeAdapter(field.annotation).dump_python(default, mode="json", warnings=False)
        if key in node:
            complete(field.annotation, node[key])


def _child(declared, node, key: str):
    """the node under key and its declared type, None when the path leaves the configuration"""
    if isinstance(node, list):
        elements = _members(declared)
        if not key.isdigit() or int(key) >= len(node) or len(elements) != 1 or get_origin(elements[0]) is not list:
            return None
        return node[int(key)], get_args(elements[0])[0]
    if not isinstance(node, dict):
        return None
    model = _model_of(declared, node)
    if model is not None:
        field = model.model_fields.get(key)
        if field is None:
            return None
        if node.get(key) is None and not _is_optional(field.annotation) and _model_of(field.annotation, {}) is not None:
            # a section left to its defaults in a configuration written by hand: the form shows it
            node[key] = {}
        return (node[key], field.annotation) if key in node else (None, field.annotation)
    plain = [m for m in _members(declared) if get_origin(m) is dict or m is dict]
    if plain:
        args = get_args(plain[0])
        return node.get(key), (args[1] if len(args) == 2 else object)
    return None


def _parent(model, config: dict, keys: list):
    declared, node = model, config
    for key in keys[:-1]:
        found = _child(declared, node, key)
        if found is None or found[0] is None:
            # an Optional left unset: the form's hidden tab, whose values the configuration ignores
            return None
        node, declared = found
    return declared, node


def set_option(model, config: dict, prefix: str, label: str) -> bool:
    keys = prefix.split(".")
    located = _parent(model, config, keys)
    if located is None:
        return False
    declared, node = located
    if isinstance(node, list):
        return _set_item_option(declared, node, keys[-1], label)
    holder = _model_of(declared, node)
    if holder is None or keys[-1] not in holder.model_fields:
        return False
    key, field_type = keys[-1], holder.model_fields[keys[-1]].annotation
    current = node.get(key)
    members = [m for m in _members(field_type) if _is_model(m)]
    by_label = [m for m in members if generate_tab_name(m, "") == label]
    if _is_optional(field_type):
        if label == NONE:
            node[key] = None
            return True
        if current is None:
            node[key] = fresh(by_label[0] if by_label else members[0]) if members else {}
            return True
    if not by_label:
        # another union of the same name without this option, or an Optional's ' ': left as it is
        return label.strip() == "" or any(generate_tab_name(m, "") == label for m in _members(field_type))
    if _model_of(field_type, current) is not by_label[0]:
        node[key] = fresh(by_label[0])
    return True


def _set_item_option(declared, items: list, index: str, label: str) -> bool:
    """a list's item set to an option, or added at the end of the list (as the form does: an operator's
    configuration may start with an empty list, the item imposed is then missing)"""
    elements = [get_args(m)[0] for m in _members(declared) if get_origin(m) is list and get_args(m)]
    if not index.isdigit() or not elements:
        return False
    options = [m for m in _members(elements[0]) if _is_model(m) and generate_tab_name(m, "") == label]
    position = int(index)
    if not options or position > len(items):
        return False
    if position == len(items):
        items.append(fresh(options[0]))
    elif _model_of(elements[0], items[position]) is not options[0]:
        items[position] = fresh(options[0])
    return True


def set_value(model, config: dict, path: str, value) -> bool:
    keys = path.split(".")
    located = _parent(model, config, keys)
    if located is None:
        return False
    declared, node = located
    if isinstance(node, list):
        if not keys[-1].isdigit() or int(keys[-1]) >= len(node):
            return False
        node[int(keys[-1])] = as_text(value)
        return True
    if not isinstance(node, dict):
        return False
    holder = _model_of(declared, node)
    if holder is not None and keys[-1] not in holder.model_fields:
        return False
    node[keys[-1]] = as_text(value)
    return True


def apply(model, config: dict, presets: dict) -> tuple[dict, list, list]:
    """the configuration with the presets, the names it has no place for (the other role's, a hidden
    tab's), and the names ignored"""
    options_set, _, values_set, _, ignored = accepted(presets)
    config = copy.deepcopy(config)
    # the options first, as the form: a value goes into the option the session selects
    unplaced = [prefix for prefix, label in options_set.items() if not set_option(model, config, prefix, str(label))]
    unplaced += [path for path, value in values_set.items() if not set_value(model, config, path, value)]
    complete(model, config)
    return config, unplaced, ignored
