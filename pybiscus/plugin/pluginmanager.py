import importlib
import importlib.util
import sys
import os
from pathlib import Path
from collections import defaultdict
from collections.abc import Mapping
import yaml

from pybiscus.core.pybiscusexception import PybiscusPluginError

# (category, module, missing dependency) of the plugins skipped by the last load_plugins
_skipped_plugins = []
# plugin module -> (category, path), from the manifest: the registries import plugins through it
_plugin_locations = {}


def load_config(path_to_config):
    with open(path_to_config, 'r') as f:
        return yaml.safe_load(f)


def get_skipped_plugins():
    return list(_skipped_plugins)


def plugins_verbose() -> bool:
    # the details of the loading made about 500 lines at every command: shown on demand only
    return os.getenv("PYBISCUS_PLUGINS_VERBOSE", "").strip().lower() in ("1", "true", "yes", "on")


def _say(message: str) -> None:
    if plugins_verbose():
        print(message)


def _strict_mode() -> bool:
    return os.getenv("PYBISCUS_PLUGINS_STRICT", "").strip().lower() in ("1", "true", "yes", "on")


def _is_own_module(missing: str, module_name: str) -> bool:
    # the plugin itself (typo in the manifest), one of its submodules or a pybiscus module:
    # a packaging mistake, not an optional dependency left uninstalled
    return (missing == module_name
            or missing.startswith(module_name + ".")
            or missing == "pybiscus" or missing.startswith("pybiscus."))


def plugin_modules(config) -> dict:
    """category -> [(path, module)] of the manifest. Every path joins sys.path before any plugin is
    imported: a plugin may import a registry whose plugins belong to a later category"""

    if not isinstance(config, Mapping):
        raise PybiscusPluginError(f"invalid plugin manifest: expected a mapping of categories, got {type(config).__name__}")

    modules = defaultdict(list)
    for category, path_module_list in config.items():
        for path_entry in path_module_list or []:
            path = path_entry.get('path')
            names = path_entry.get('modules', [])

            if names is None:
                _say(f"  ⚠️ No module 🧩 defined in path 📦 {path}")
                continue

            if not path or not os.path.isdir(path):
                raise PybiscusPluginError(f"invalid or missing plugin path 📦 '{path}' (category '{category}')")

            if path not in sys.path:
                sys.path.append(path)
                _say(f"  ✅ Added 📦 '{path}' to sys.path")

            for module_name in names:
                modules[category].append((path, module_name))
                _plugin_locations[module_name] = (category, path)
    return modules


def _check_not_shadowed(category: str, path: str, module_name: str) -> None:
    # plugins are top-level modules (their directory is on sys.path): a name taken by the standard
    # library or an installed package resolves to that module, not to the plugin (the reason for
    # the trailing underscore of the wandb_ plugin)
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise PybiscusPluginError(f"plugin 🧩 '{module_name}' (category '{category}') not found in path 📦 '{path}'")
    origin = spec.origin if spec.origin not in (None, "built-in", "frozen") else None
    if origin is None and spec.submodule_search_locations:
        origin = next(iter(spec.submodule_search_locations))
    if origin is None or not Path(origin).resolve().is_relative_to(Path(path).resolve()):
        raise PybiscusPluginError(
            f"plugin 🧩 '{module_name}' (category '{category}') is shadowed by '{origin or spec.origin}': "
            f"another module has this name, rename the plugin"
        )


def import_plugin(module_name: str):
    """the plugin module, or None when it is skipped (a missing third-party dependency)"""

    category, path = _plugin_locations[module_name]
    if any(skipped == module_name for _, skipped, _ in _skipped_plugins):
        return None
    _check_not_shadowed(category, path, module_name)
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name is None or _is_own_module(e.name, module_name):
            raise PybiscusPluginError(
                f"plugin 🧩 '{module_name}' (category '{category}') not found in path 📦 '{path}': {e}"
            ) from e
        if _strict_mode():
            raise PybiscusPluginError(
                f"plugin 🧩 '{module_name}' (category '{category}') needs the missing module '{e.name}' "
                f"(PYBISCUS_PLUGINS_STRICT is set)"
            ) from e
        _skipped_plugins.append((category, module_name, e.name))
        print(f"  ⚠️ 🧩 Plugin '{module_name}' skipped: missing dependency '{e.name}'")
        return None
    except PybiscusPluginError:
        raise
    except Exception as e:
        raise PybiscusPluginError(
            f"plugin 🧩 '{module_name}' (category '{category}') failed to import: {type(e).__name__}: {e}"
        ) from e


def is_plugin(module_name: str) -> bool:
    return module_name in _plugin_locations


def load_plugins(config, verbose=False):

    # a library must not end the process (it also serves the agent and the manager): errors are
    # raised, the entry points decide. Only a missing third-party dependency is tolerated, so
    # that plugins with uninstalled optional dependencies do not take down the others
    _skipped_plugins.clear()
    _say("🔍 [plugins] Processing Pybiscus plugins 🧩")
    modules = plugin_modules(config)

    result = defaultdict(list)
    for category, entries in modules.items():
        _say(f" 🔍 [plugins] Processing category '{category}'...")
        for _, module_name in entries:
            if import_plugin(module_name) is not None:
                result[category].append(module_name)
                _say(f"  ✅ 🧩 Successfully imported plugin '{module_name}'")

    loaded = sum(len(names) for names in result.values())
    print(f"🧩 [plugins] {loaded} plugin(s) loaded"
          + (f", {len(_skipped_plugins)} skipped: " + ", ".join(f"'{m}' (missing '{d}')" for _, m, d in _skipped_plugins)
             if _skipped_plugins else "")
          + ("" if plugins_verbose() else " (details: PYBISCUS_PLUGINS_VERBOSE=1)"))

    return result
