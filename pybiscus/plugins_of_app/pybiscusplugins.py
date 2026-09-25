
_plugins_by_category = None

def get_plugins_by_category():

    global _plugins_by_category

    if _plugins_by_category is None:

        from pybiscus.commands.apps_common import load_config_with_env
        from pybiscus.core.pybiscusexception import PybiscusPluginError
        from pybiscus.plugin.pluginmanager import load_plugins

        # an unreadable manifest used to degrade silently to "no plugin", which only surfaced
        # later as obscure validation errors
        try:
            config = load_config_with_env(env_var = "PYBISCUS_PLUGIN_CONF_PATH", default = "pybiscus-plugins-conf.yml")
        except Exception as e:
            raise PybiscusPluginError(f"cannot read the plugin manifest(s): {e}") from e

        _plugins_by_category = load_plugins(config, verbose=True)

    return _plugins_by_category
    
    

if __name__ == "__main__":

    plugins_by_category = get_plugins_by_category()
    print(plugins_by_category)
    print(plugins_by_category["data"])
    print(plugins_by_category["model"])
    print(plugins_by_category["metricslogger"])
