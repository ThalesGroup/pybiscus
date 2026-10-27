import importlib.util
import keyword
import re
from pathlib import Path
from string import Template

import yaml

from pybiscus.core.pybiscusexception import PybiscusPluginError
from pybiscus.plugin.plugindeps import REQUIREMENTS_FILE

TEMPLATES = Path(__file__).parent / "templates"
MANIFEST = "plugins-conf.yml"
EXAMPLES = "examples"

# the third-party packages each template imports: the generated requirements.txt
REQUIREMENTS = {
    "model": ["lightning", "pydantic", "torch"],
    "data": ["lightning", "pydantic", "torch"],
    "strategydecorator": ["pydantic"],
}
KINDS = tuple(REQUIREMENTS)

FEATURES = 4


def class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def check_name(name: str, plugins_dir: Path, taken_keys) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise PybiscusPluginError(f"'{name}': a plugin's name is a lowercase Python identifier (a-z, 0-9, _)")
    if name in taken_keys:
        raise PybiscusPluginError(f"'{name}' is already the name of a plugin of this family")
    # plugins are top-level modules: an installed package or another plugin of that name would be
    # imported instead of it
    spec = importlib.util.find_spec(name)
    if spec is not None:
        raise PybiscusPluginError(f"'{name}' is already a module ({spec.origin or name}): choose another name")
    if (plugins_dir / name).exists():
        raise PybiscusPluginError(f"{plugins_dir / name} exists already")


def render(kind: str, name: str) -> dict[str, str]:
    """file name -> content, of the plugin package"""
    values = {"name": name, "Name": class_name(name)}
    files = {}
    for template in sorted((TEMPLATES / kind).glob("*.tmpl")):
        target = template.name.removesuffix(".tmpl").replace("MODULE", name)
        files[target] = Template(template.read_text(encoding="utf-8")).substitute(values)
    files[REQUIREMENTS_FILE] = "".join(f"{r}\n" for r in REQUIREMENTS[kind])
    return files


def _server(data: dict, model: dict, pipeline: list) -> dict:
    return {
        "root_dir": "${oc.env:PWD}",
        "flower_server": {"listen_address": "[::1]:3333"},
        "server_run": {
            "num_rounds": 2,
            "clients_fit_local_epochs": 1,
            "loggers": [{"name": "rich", "config": {"empty_configuration": True}}],
            "reporting": {"basedir": "${root_dir}/experiments", "add_timestamp_in_path": True,
                          "server_config_filename": "config_server.yml",
                          "save_on_train_end": {"filename": "final_checkpoint.pt"}},
        },
        "server_compute_context": {"hardware": {"accelerator": "auto", "devices": "auto"}, "metrics_loggers": []},
        "server_strategy": {
            "pipeline": pipeline,
            "strategy": {"name": "fedavg", "config": {
                "fraction_fit": 1, "fraction_evaluate": 1, "min_fit_clients": 2, "min_evaluate_clients": 2,
                "min_available_clients": 2, "accept_failures": True, "inplace": True}},
        },
        "data": data,
        "model": model,
    }


def _client(cid: int, data: dict, model: dict) -> dict:
    return {
        "root_dir": "${oc.env:PWD}",
        "flower_client": {"server_address": "localhost:3333"},
        "client_run": {"cid": str(cid), "pre_train_val": False},
        "client_compute_context": {"hardware": {"accelerator": "auto", "devices": "auto"}},
        "model": model,
        "data": data,
    }


def examples(kind: str, name: str) -> dict[str, dict]:
    """a session of two clients with the new plugin and bundled ones that fit it (synthetic data:
    nothing to download)"""
    if kind == "data":
        model = {"name": "linearregression", "config": {"input_dim": FEATURES, "output_dim": 1}}
        data_name = name
    else:
        model = ({"name": name, "config": {"input_dim": FEATURES}} if kind == "model"
                 else {"name": "linearregression", "config": {"input_dim": FEATURES, "output_dim": FEATURES}})
        data_name = "randomvector"
    pipeline = [{"name": name, "config": {"every": 1}}] if kind == "strategydecorator" else []

    def data(partition_id=None):
        config = {"feature_dim": FEATURES}
        if partition_id is not None:
            config["train"] = {"partition": {"num_partitions": 2, "partition_id": partition_id}}
        return {"name": data_name, "config": config}

    return {"server.yml": _server(data(), model, pipeline),
            "client_1.yml": _client(0, data(0), model),
            "client_2.yml": _client(1, data(1), model)}


def add_to_manifest(manifest: Path, category: str, name: str) -> None:
    """appends the module under `category: - path: "./<category>"`, keeping the file's comments"""
    entry_path = f"./{category}"
    lines = manifest.read_text(encoding="utf-8").splitlines() if manifest.is_file() else [
        "# Plugins of this directory: add it to PYBISCUS_PLUGIN_CONF_PATH (colon-separated) to load them.",
        "# Paths are relative to this file."]
    config = yaml.safe_load("\n".join(lines)) or {}
    new_entry = [f'  - path: "{entry_path}"', "    modules:", f"      - {name}"]
    if category not in config:
        lines += [f"{category}:", *new_entry]
    else:
        # within the category's block: the last module line of its entry for that path, else the
        # block's last line (a second `category:` key would silently replace the first one)
        in_category = in_entry = False
        module_at = indent = None
        block_end = None
        for i, line in enumerate(lines):
            if re.match(rf"^{category}:\s*$", line):
                in_category, block_end = True, i
                continue
            if in_category and re.match(r"^\S", line):
                break
            if not in_category:
                continue
            if line.strip() and not line.lstrip().startswith("#"):
                block_end = i
            if re.match(r"^\s*-\s*path:", line):
                in_entry = yaml.safe_load(line.strip()[1:].strip())["path"] in (entry_path, category)
            elif in_entry and re.match(r"^\s*-\s*[\w.]+\s*$", line):
                module_at, indent = i, line[:len(line) - len(line.lstrip())]
        if module_at is not None:
            lines.insert(module_at + 1, f"{indent}- {name}")
        elif block_end is not None:
            lines[block_end + 1:block_end + 1] = new_entry
        else:
            raise PybiscusPluginError(f"{manifest}: cannot find where to list '{name}' under {category}: add it by hand")
    text = "\n".join(lines) + "\n"
    listed = [m for e in (yaml.safe_load(text).get(category) or []) for m in (e.get("modules") or [])]
    if name not in listed:
        raise PybiscusPluginError(f"{manifest}: '{name}' could not be listed under {category}: add it by hand")
    manifest.write_text(text, encoding="utf-8")


def create(kind: str, name: str, root: Path, taken_keys) -> Path:
    category_dir = root / kind
    check_name(name, category_dir, taken_keys)
    files = render(kind, name)
    package = category_dir / name
    (package / EXAMPLES).mkdir(parents=True)
    for file, content in files.items():
        (package / file).write_text(content, encoding="utf-8")
    for file, content in examples(kind, name).items():
        (package / EXAMPLES / file).write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")
    add_to_manifest(root / MANIFEST, kind, name)
    return package
