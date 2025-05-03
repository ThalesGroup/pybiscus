import importlib
import sys
import os
from collections import defaultdict
import yaml

def load_config(path_to_config):
    with open(path_to_config, 'r') as f:
        return yaml.safe_load(f)

def load_plugins(config, verbose=False):

    result = defaultdict(list)

    print(f"🔍 [plugins] Processing Pybiscus plugins 🧩")

    for category, path_module_list in config.items():
        print(f" 🔍 [plugins] Processing category '{category}'...")
        
        for path_entry in path_module_list:
            path = path_entry.get('path')
            modules = path_entry.get('modules', [])

            if modules is None:
                print(f"  ⚠️ No module 🧩 defined in path 📦 {path}")
            else:
                if not path or not os.path.isdir(path):
                    print(f"  ⚠️ Invalid or missing path: 📦 {path}")
                    continue

                if path not in sys.path:
                    sys.path.append(path)
                    print(f"  ✅ Added 📦 '{path}' to sys.path")

                for module_name in modules:
                    try:
                        importlib.import_module(module_name)
                        result[category].append(module_name)
                        print(f"  ✅ 🧩 Successfully imported plugin '{module_name}'")
                    except ImportError as e:
                        print(f"  ❌ Failed to import plugin 🧩 '{module_name}' from path 📦 '{path}': {e}")

    return result

def get_plugins_by_category():
    config_file_path = os.getenv('PYBISCUS_PLUGIN_CONF_PATH', "pybiscus-plugins-conf.yml")
    print(f"🔍 [plugins] Using config file: {config_file_path}")
    config = load_config(config_file_path)
    plugins_by_category = load_plugins(config, verbose=True)
    return plugins_by_category

if __name__ == "__main__":

    plugins_by_category = get_plugins_by_category()
    print(plugins_by_category)
    print(plugins_by_category["data"])
    print(plugins_by_category["model"])
    print(plugins_by_category["loggerfactory"])
