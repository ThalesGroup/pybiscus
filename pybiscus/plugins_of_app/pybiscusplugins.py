
_plugins_by_category = None

def get_plugins_by_category():

    global _plugins_by_category

    if _plugins_by_category is None:

        try:
            from pybiscus.commands.apps_common import load_config_with_env
            from pybiscus.plugin.pluginmanager import load_plugins

            config = load_config_with_env(env_var = "PYBISCUS_PLUGIN_CONF_PATH", default = "pybiscus-plugins-conf.yml")
            _plugins_by_category = load_plugins(config, verbose=True)

        except Exception as e:

            from collections import defaultdict

            print(f"❌ Can not load pybiscus plugins {e}")
            _plugins_by_category = defaultdict(list)

    return _plugins_by_category
    
    

if __name__ == "__main__":

    plugins_by_category = get_plugins_by_category()
    print(plugins_by_category)
    print(plugins_by_category["data"])
    print(plugins_by_category["model"])
    print(plugins_by_category["metricslogger"])
