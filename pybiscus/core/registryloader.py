from typing import Generic, Literal, TypeVar, Type, Dict, Optional, List, Tuple, Union, get_args, get_origin
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from pathlib import Path
import importlib
import pkgutil

from importlib.metadata import inspect


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
        self.verbose = verbose

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
        config_classes: List[Type[BaseModel]] = []

        for full_module_name in packages:

            try:
                mod = importlib.import_module(full_module_name)

                if self.verbose:
                    print(f"📦 Loading module: {full_module_name}")

                if hasattr(mod, "get_modules_and_configs"):

                    # print(f"🔍 Content of {full_module_name} :")
                    # for name in dir(mod):
                    #     if not name.startswith("__"):
                    #         attr = getattr(mod, name)
                    #         print(f" - {name}: {type(attr)}")
                    #         if inspect.isfunction(attr):
                    #             print(f"   (function) {name}{inspect.signature(attr)}")
                    #         elif inspect.isclass(attr):
                    #             print(f"   (class) {name}")                    

                    sub_registry, sub_configs = mod.get_modules_and_configs()

                    for key, cls in sub_registry.items():
                        if issubclass(cls, self.expected_class):
                            registry[key] = cls
                            if self.verbose:
                                print(f"  ✅ Registered: {key} ({cls.__name__})")
                        else:
                            if self.verbose:
                                print(f"  ⚠️ Skipped '{key}'->'{cls.__name__}': Not a subclass of {self.expected_class.__name__}")

                    if full_module_name.startswith("pybiscus."):
                        origin_marker = "core"
                    else:
                        origin_marker = "plugin"

                    # sanity check : filtering out classes not deriving from BaseModel

                    configs_ok, configs_ko = partition( lambda config : issubclass(config, BaseModel), sub_configs )

                    for config in configs_ok:
                        setattr( config, 'PYBISCUS_MODULE_ORIGIN', origin_marker )

                    # register correct classes
                    config_classes.extend(configs_ok)

                    # remove factory classes associated to bad config classes
                    for config in configs_ko:
                        print(f"⚠️ Skipped '{config.__name__}' as does not derive from BaseModel")
                        config_name = get_name_value_if_literal(config)
                        if config_name is not None:
                            cls = registry.pop(config_name,None)
                            print(f"  🗑️ Forget registry '{key}'->{cls.__name__}: associated config class is incorrect")

                elif self.verbose:
                    print(f"⚠️  No get_modules_and_configs() in {full_module_name}")
                    print(f"🔍 Content of {full_module_name} :")
                    for name in dir(mod):
                        if not name.startswith("__"):
                            attr = getattr(mod, name)
                            print(f" - {name}: {type(attr)}")
                            if inspect.isfunction(attr):
                                print(f"   (function) {name}{inspect.signature(attr)}")
                            elif inspect.isclass(attr):
                                print(f"   (class) {name}")                    

            except Exception as e:
                if self.verbose:
                    print(f"❌ Error loading {full_module_name}: {e}")

        config_union = (
            Annotated[Union[*config_classes], Field(discriminator="name")]
            if config_classes
            else None
        )

        if self.verbose:
            print(f"\n📦 Total {self.expected_class.__name__}(s) registered: {len(registry)}")
            print(f"🧩 Total configs in union: {len(config_classes)}\n")

        return registry, config_union

