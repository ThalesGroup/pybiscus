import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Tuple, Type, Union, Optional
from pydantic import BaseModel, Field
from typing_extensions import Annotated
import lightning.pytorch as pl

def register_from_path(
    base_package: str,
    expected_class: Union[Type[pl.LightningDataModule], Type[pl.LightningModule]],
    verbose: bool = True
) -> Tuple[Dict[str, Type], Optional[type]]:
    """
    Scans submodules of the given base_package and calls get_modules_and_configs()
    to register components and produce a config union for Pydantic models.

    Args:
        base_package: Python package path (e.g. 'pybiscus.ml.data')
        expected_class: Type to filter components (e.g. LightningDataModule or LightningModule)
        verbose: Whether to print logs during registration

    Returns:
        Tuple of:
            - registry: Dict[str, Lightning class]
            - config_union: Annotated Union[...] with Field(discriminator="name"), or None
    """
    registry: Dict[str, Type] = {}
    config_classes: List[Type[BaseModel]] = []

    package = importlib.import_module(base_package)
    package_path = Path(package.__file__).parent

    if verbose:
        print(f"🔍 [registry] Scanning submodules in: {base_package} ({package_path})")

    for _, submodule_name, _ in pkgutil.iter_modules([str(package_path)]):
        full_module_name = f"{base_package}.{submodule_name}"
        try:
            mod = importlib.import_module(full_module_name)

            if verbose:
                print(f"📦 Loading module: {full_module_name}")

            if hasattr(mod, "get_modules_and_configs"):
                sub_registry, sub_configs = mod.get_modules_and_configs()

                for key, cls in sub_registry.items():
                    if issubclass(cls, expected_class):
                        registry[key] = cls
                        if verbose:
                            print(f"  ✅ Registered: {key} ({cls.__name__})")
                    else:
                        if verbose:
                            print(f"  ⚠️ Skipped '{key}'->'{cls.__name__}': Not a subclass of {expected_class.__name__}")

                config_classes.extend(sub_configs)
            elif verbose:
                print(f"⚠️  No get_modules_and_configs() in {full_module_name}")
        except Exception as e:
            if verbose:
                print(f"❌ Error loading {full_module_name}: {e}")

    if config_classes:
        config_union = Annotated[
            Union[tuple(config_classes)],
            Field(discriminator="name")
        ]
    else:
        config_union = None

    if verbose:
        print(f"\n📦 Total {expected_class.__name__}s registered: {len(registry)}")
        print(f"🧩 Total configs in union: {len(config_classes)}\n")

    return registry, config_union

#### --- Data Modules ---

datamodule_registry, DataConfig = register_from_path("pybiscus.ml.data", pl.LightningDataModule, True)

#### --- Models ---

model_registry, ModelConfig = register_from_path("pybiscus.ml.models", pl.LightningModule, True)
