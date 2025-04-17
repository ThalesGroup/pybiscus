from typing import Generic, TypeVar, Type, Dict, Optional, List, Tuple, Union
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from pathlib import Path
import importlib
import pkgutil

T = TypeVar("T")

class RegistryLoader(Generic[T]):
    def __init__(self, expected_class: Type[T], verbose: bool = True):
        self.expected_class = expected_class
        self.verbose = verbose

    def register_from_path(
        self, base_package: str
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

        package = importlib.import_module(base_package)
        package_path = Path(package.__file__).parent

        if self.verbose:
            print(f"🔍 [registry] Scanning submodules in: {base_package} ({package_path})")

        for _, submodule_name, _ in pkgutil.iter_modules([str(package_path)]):
            full_module_name = f"{base_package}.{submodule_name}"
            try:
                mod = importlib.import_module(full_module_name)

                if self.verbose:
                    print(f"📦 Loading module: {full_module_name}")

                if hasattr(mod, "get_modules_and_configs"):
                    sub_registry, sub_configs = mod.get_modules_and_configs()

                    for key, cls in sub_registry.items():
                        if issubclass(cls, self.expected_class):
                            registry[key] = cls
                            if self.verbose:
                                print(f"  ✅ Registered: {key} ({cls.__name__})")
                        else:
                            if self.verbose:
                                print(f"  ⚠️ Skipped '{key}'->'{cls.__name__}': Not a subclass of {self.expected_class.__name__}")

                    config_classes.extend(sub_configs)
                elif self.verbose:
                    print(f"⚠️  No get_modules_and_configs() in {full_module_name}")
            except Exception as e:
                if self.verbose:
                    print(f"❌ Error loading {full_module_name}: {e}")

        config_union = (
            Annotated[Union[tuple(config_classes)], Field(discriminator="name")]
            if config_classes
            else None
        )

        if self.verbose:
            print(f"\n📦 Total {self.expected_class.__name__}s registered: {len(registry)}")
            print(f"🧩 Total configs in union: {len(config_classes)}\n")

        return registry, config_union
