import importlib
import sys
import os
from collections import defaultdict
from collections.abc import Mapping
import yaml

from pybiscus.core.pybiscusexception import PybiscusPluginError

# (category, module, missing dependency) of the plugins skipped by the last load_plugins
_skipped_plugins = []


def load_config(path_to_config):
    with open(path_to_config, 'r') as f:
        return yaml.safe_load(f)


def get_skipped_plugins():
    return list(_skipped_plugins)


def _strict_mode() -> bool:
    return os.getenv("PYBISCUS_PLUGINS_STRICT", "").strip().lower() in ("1", "true", "yes", "on")


def _is_own_module(missing: str, module_name: str) -> bool:
    # the plugin itself (typo in the manifest), one of its submodules or a pybiscus module:
    # a packaging mistake, not an optional dependency left uninstalled
    return (missing == module_name
            or missing.startswith(module_name + ".")
            or missing == "pybiscus" or missing.startswith("pybiscus."))


def load_plugins(config, verbose=False):

    # a library must not end the process (it also serves the agent and the manager): errors are
    # raised, the entry points decide. Only a missing third-party dependency is tolerated, so
    # that plugins with uninstalled optional dependencies do not take down the others
    result = defaultdict(list)
    _skipped_plugins.clear()
    strict = _strict_mode()

    print(f"🔍 [plugins] Processing Pybiscus plugins 🧩")

    if not isinstance(config, Mapping):
        raise PybiscusPluginError(f"invalid plugin manifest: expected a mapping of categories, got {type(config).__name__}")

    for category, path_module_list in config.items():
        print(f" 🔍 [plugins] Processing category '{category}'...")

        for path_entry in path_module_list or []:
            path = path_entry.get('path')
            modules = path_entry.get('modules', [])

            if modules is None:
                print(f"  ⚠️ No module 🧩 defined in path 📦 {path}")
                continue

            if not path or not os.path.isdir(path):
                raise PybiscusPluginError(f"invalid or missing plugin path 📦 '{path}' (category '{category}')")

            if path not in sys.path:
                sys.path.append(path)
                print(f"  ✅ Added 📦 '{path}' to sys.path")

            for module_name in modules:
                try:
                    importlib.import_module(module_name)
                except ModuleNotFoundError as e:
                    if e.name is None or _is_own_module(e.name, module_name):
                        raise PybiscusPluginError(
                            f"plugin 🧩 '{module_name}' (category '{category}') not found in path 📦 '{path}': {e}"
                        ) from e
                    if strict:
                        raise PybiscusPluginError(
                            f"plugin 🧩 '{module_name}' (category '{category}') needs the missing module '{e.name}' "
                            f"(PYBISCUS_PLUGINS_STRICT is set)"
                        ) from e
                    _skipped_plugins.append((category, module_name, e.name))
                    print(f"  ⚠️ 🧩 Plugin '{module_name}' skipped: missing dependency '{e.name}'")
                    continue
                except Exception as e:
                    raise PybiscusPluginError(
                        f"plugin 🧩 '{module_name}' (category '{category}') failed to import: {type(e).__name__}: {e}"
                    ) from e

                result[category].append(module_name)
                print(f"  ✅ 🧩 Successfully imported plugin '{module_name}'")

    if _skipped_plugins:
        print(f"⚠️ [plugins] {len(_skipped_plugins)} plugin(s) skipped: "
              + ", ".join(f"'{m}' (missing '{d}')" for _, m, d in _skipped_plugins))

    return result
