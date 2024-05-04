def change_conf_with_args(config: dict, **kwargs) -> dict:
    """Change inplace the config dictionary with non trivial kwargs."""
    for key, val in kwargs.items():
        if val:
            config[key] = val
    return config
