import re

# OmegaConf resolves the configuration on the agent's machine: an interpolation calling a resolver
# (${oc.env:NAME}, ${oc.decode:...}) reads that machine, and a value the manager imposes could carry
# one back to it (the reports' path is logged to the manager). A plain reference (${root_dir}) only
# reads the same configuration: the manager proposes one itself.
RESOLVER_CALL = re.compile(r"\$\{[^}]*:")


def calls_resolver(value) -> bool:
    return isinstance(value, str) and bool(RESOLVER_CALL.search(value))


def resolver_paths(tree, prefix: str = "") -> list:
    """the dotted paths of the strings of a JSON tree that call a resolver"""
    if isinstance(tree, dict):
        return [path for key, value in tree.items() for path in resolver_paths(value, f"{prefix}{key}.")]
    if isinstance(tree, list):
        return [path for i, value in enumerate(tree) for path in resolver_paths(value, f"{prefix}{i}.")]
    return [prefix.rstrip(".")] if calls_resolver(tree) else []
