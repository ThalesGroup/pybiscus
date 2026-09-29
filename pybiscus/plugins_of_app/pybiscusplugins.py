
_plugins_by_category = None
_names_while_loading = None

def get_plugins_by_category():
    global _plugins_by_category, _names_while_loading
    if _plugins_by_category is not None:
        return _plugins_by_category
    # a plugin being imported may import the registry of another category, which asks again: it
    # gets the manifest's names (the registry applies the same import policy) instead of a second,
    # nested loading, which read the manifest three times and cleared the list of skipped plugins
    if _names_while_loading is not None:
        return _names_while_loading

    from collections import defaultdict
    from pybiscus.commands.apps_common import load_config_with_env
    from pybiscus.core.pybiscusexception import PybiscusPluginError
    from pybiscus.plugin.pluginmanager import load_plugins, plugin_modules
    # an unreadable manifest used to degrade silently to "no plugin", which only surfaced
    # later as obscure validation errors
    try:
        config = load_config_with_env(env_var = "PYBISCUS_PLUGIN_CONF_PATH", default = "pybiscus-plugins-conf.yml")
    except Exception as e:
        raise PybiscusPluginError(f"cannot read the plugin manifest(s): {e}") from e

    _names_while_loading = defaultdict(list, {category: [name for _, name in entries]
                                              for category, entries in plugin_modules(config).items()})
    try:
        _plugins_by_category = load_plugins(config, verbose=True)
    finally:
        _names_while_loading = None
    return _plugins_by_category

if __name__ == "__main__":

    plugins_by_category = get_plugins_by_category()
    print(plugins_by_category)
    print(plugins_by_category["data"])
    print(plugins_by_category["model"])
    print(plugins_by_category["metricslogger"])
