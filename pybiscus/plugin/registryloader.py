from typing import Generic, Literal, TypeVar, Type, Dict, Optional, List, Tuple, Union, get_args, get_origin
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from pathlib import Path
import importlib
import inspect
import pkgutil

from pybiscus.core.pybiscusexception import PybiscusPluginError
from pybiscus.plugin.pluginmanager import import_plugin, is_plugin, plugins_verbose


def get_name_value_if_literal(cls):
    annotation = cls.__annotations__.get('name')

    if get_origin(annotation) is Literal:
        value = get_args(annotation)[0]  # -> "webhook"
        return value
    
    return None


def partition(pred, iterable):
    yes, no = [], []
    for x in iterable:
        (yes if pred(x) else no).append(x)
    return yes, no


T = TypeVar("T")

class RegistryLoader(Generic[T]):

    def __init__(self, expected_class: Type[T], verbose: bool = True):
        self.expected_class = expected_class
        # the details are shown on demand only (PYBISCUS_PLUGINS_VERBOSE): about 500 lines otherwise
        self.verbose = verbose and plugins_verbose()

    def get_submodules_from_path(self, base_package: str) -> List[str]:
        # print(f"Trying to import base_package: {base_package}")

        try:
            package = importlib.import_module(base_package)
        except ImportError as e:
            print(f"❌ [registry] Failed to import base package {base_package}: {e}")
            return []

        package_file = getattr(package, "__file__", None)
        if not package_file:
            print(f"⚠️ [registry] Package {base_package} has no __file__ attribute (probably built-in or namespace package).")
            return []

        package_path = Path(package_file).parent

        if self.verbose:
            print(f"🔍 [registry] Scanning submodules in: {base_package} ({package_path})")

        submodules = [
            f"{base_package}.{submodule_name}"
            for _, submodule_name, _ in pkgutil.iter_modules([str(package_path)])
        ]

        if self.verbose:
            print(f"✅ [registry] Found submodules: {submodules}")

        return submodules

    def register_modules(
        self, packages: List[str]
    ) -> Tuple[Dict[str, Type[T]], Optional[Annotated[Union[BaseModel], Field(discriminator="name")]]]:
        
        """
        Scans submodules of the given base_package and calls get_modules_and_configs()
        to register components and produce a config union for Pydantic models.

        Args:
            base_package: Python package path (e.g. 'pybiscus.ml.data')
            expected_class: Type to filter components
            verbose: Whether to print logs during registration

        Returns:
            Tuple of:
                - registry: Dict[str, expected_class]
                - config_union: Annotated Union[...] with Field(discriminator="name"), or None
    """
        registry: Dict[str, Type[T]] = {}
        registered_by: Dict[str, str] = {}
        config_classes: List[Type[BaseModel]] = []

        for full_module_name in packages:

            try:
                # plugins go through the plugin manager: shadowing check, missing-dependency policy
                mod = import_plugin(full_module_name) if is_plugin(full_module_name) else importlib.import_module(full_module_name)
                if mod is None:
                    continue

                if self.verbose:
                    print(f"📦 Loading module: {full_module_name}")

                if not hasattr(mod, "get_modules_and_configs"):
                    if self.verbose:
                        print(f"⚠️  No get_modules_and_configs() in {full_module_name}")
                        for name in dir(mod):
                            if not name.startswith("__"):
                                attr = getattr(mod, name)
                                if inspect.isfunction(attr):
                                    print(f"   (function) {name}{inspect.signature(attr)}")
                                elif inspect.isclass(attr):
                                    print(f"   (class) {name}")
                    continue

                sub_registry, sub_configs = mod.get_modules_and_configs()

                # sanity check : filtering out classes not deriving from BaseModel
                configs_ok, configs_ko = partition(lambda config: isinstance(config, type) and issubclass(config, BaseModel), sub_configs)
                for config in configs_ko:
                    config_name = get_name_value_if_literal(config) if isinstance(config, type) else None
                    dropped = sub_registry.pop(config_name, None) if config_name is not None else None
                    print(f"⚠️ Skipped config '{getattr(config, '__name__', config)}' of {full_module_name}: it does not derive from BaseModel"
                          + (f"; its registry entry '{config_name}' ({dropped.__name__}) is dropped too" if dropped is not None else ""))

                # a registry key and the "name" of its config are declared apart: a mismatch passed
                # the configuration check and only failed at launch, on a KeyError of the registry
                names = {get_name_value_if_literal(config) for config in configs_ok} - {None}
                if names != set(sub_registry):
                    raise PybiscusPluginError(
                        f"{full_module_name}: registry keys and configuration names differ: "
                        f"keys without a configuration {sorted(set(sub_registry) - names) or '—'}, "
                        f"configurations without a key {sorted(names - set(sub_registry)) or '—'}"
                    )

                for key, cls in sub_registry.items():
                    if not issubclass(cls, self.expected_class):
                        if self.verbose:
                            print(f"  ⚠️ Skipped '{key}'->'{cls.__name__}': Not a subclass of {self.expected_class.__name__}")
                        continue
                    # a second module with the same key replaced the first one silently
                    if key in registry:
                        raise PybiscusPluginError(
                            f"registry key '{key}' ({self.expected_class.__name__}) declared by both "
                            f"{registered_by[key]} and {full_module_name}"
                        )
                    registry[key] = cls
                    registered_by[key] = full_module_name
                    if self.verbose:
                        print(f"  ✅ Registered: {key} ({cls.__name__})")

                origin_marker = "core" if full_module_name.startswith("pybiscus.") else "plugin"
                for config in configs_ok:
                    setattr( config, 'PYBISCUS_MODULE_ORIGIN', origin_marker )

                # register correct classes
                config_classes.extend(configs_ok)

            except PybiscusPluginError:
                raise
            except Exception as e:
                # raised whatever the verbosity: a quiet registry used to drop the module silently
                raise PybiscusPluginError(f"cannot register {full_module_name}: {type(e).__name__}: {e}") from e

        config_union = (
            Annotated[Union[*config_classes], Field(discriminator="name")]
            if config_classes
            else None
        )

        if self.verbose:
            print(f"\n📦 Total {self.expected_class.__name__}(s) registered: {len(registry)}")
            print(f"🧩 Total configs in union: {len(config_classes)}\n")

        return registry, config_union

