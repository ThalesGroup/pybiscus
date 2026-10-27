import ast
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Optional

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

REQUIREMENTS_FILE = "requirements.txt"


@dataclass
class RequirementState:
    requirement: Requirement
    installed: Optional[str]
    # its marker excludes this platform: neither needed nor missing here
    applies: bool = True
    missing_extras: list[str] = field(default_factory=list)

    @property
    def satisfied(self) -> bool:
        return not self.applies or (self.installed is not None and not self.missing_extras
                                    and self.requirement.specifier.contains(self.installed, prereleases=True))


@dataclass
class PluginDeps:
    category: str
    module: str
    location: Path
    # None: no requirements.txt
    requirements: Optional[list[RequirementState]]
    errors: list[str] = field(default_factory=list)
    # import name -> the files importing it, for the third-party imports no requirement covers
    undeclared: dict[str, list[str]] = field(default_factory=dict)

    @property
    def missing(self) -> list[Requirement]:
        return [s.requirement for s in self.requirements or [] if not s.satisfied]


def plugin_location(path: str, module: str) -> Path:
    package = Path(path) / module
    return package if package.is_dir() else package.with_suffix(".py")


def read_requirements(file: Path) -> tuple[list[Requirement], list[str]]:
    requirements, errors = [], []
    for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            requirements.append(Requirement(line))
        except InvalidRequirement as e:
            errors.append(f"{file.name}:{number}: '{line}' is not a requirement ({str(e).splitlines()[0]})")
    return requirements, errors


def requirement_state(requirement: Requirement) -> RequirementState:
    if requirement.marker is not None and not requirement.marker.evaluate():
        return RequirementState(requirement, None, applies=False)
    try:
        installed = metadata.version(requirement.name)
    except metadata.PackageNotFoundError:
        return RequirementState(requirement, None)
    return RequirementState(requirement, installed, missing_extras=missing_extra_requirements(requirement))


def missing_extra_requirements(requirement: Requirement) -> list[str]:
    # torchmetrics[detection] installed without its extra: torchmetrics is there, its detection is not
    missing = []
    for line in metadata.requires(requirement.name) or []:
        dependency = Requirement(line)
        if dependency.marker is None or not any(dependency.marker.evaluate({"extra": e}) for e in requirement.extras):
            continue
        if dependency.marker.evaluate({"extra": ""}):
            continue
        try:
            metadata.version(dependency.name)
        except metadata.PackageNotFoundError:
            missing.append(dependency.name)
    return missing


def pybiscus_extras(requirements: list[Requirement]) -> set[str]:
    """Pybiscus's extras that provide these requirements, when they all are in one"""
    try:
        declared = [Requirement(line) for line in metadata.requires("pybiscus") or []]
        all_extras = metadata.metadata("pybiscus").get_all("Provides-Extra") or []
    except metadata.PackageNotFoundError:
        return set()
    extras = set()
    for requirement in requirements:
        providing = {extra for extra in all_extras for d in declared
                     if d.marker is not None and canonicalize_name(d.name) == canonicalize_name(requirement.name)
                     and d.marker.evaluate({"extra": extra})}
        if not providing:
            return set()
        extras |= providing
    return extras


def _optional_import(node: ast.AST, parents: dict) -> bool:
    # inside `try: import x  except ImportError:` the plugin runs without x
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.Try) and any(
                isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError")
                or isinstance(h.type, ast.Tuple) and any(getattr(e, "id", "") in ("ImportError", "ModuleNotFoundError")
                                                         for e in h.type.elts)
                for h in node.handlers):
            return True
    return False


def imported_names(location: Path) -> dict[str, list[str]]:
    """top-level name -> files, for every absolute import of the plugin's sources"""
    files = sorted(location.rglob("*.py")) if location.is_dir() else [location]
    found: dict[str, set[str]] = {}
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            if _optional_import(node, parents):
                continue
            for name in names:
                found.setdefault(name.split(".")[0], set()).add(file.name)
    return {name: sorted(files) for name, files in found.items()}


def third_party(names: dict[str, list[str]], local: set[str]) -> dict[str, list[str]]:
    return {name: files for name, files in names.items()
            if name not in sys.stdlib_module_names and name != "pybiscus" and name not in local
            and not name.startswith("_")}


def local_modules(paths: set[str]) -> set[str]:
    # every plugin directory joins sys.path: what lies there is imported as a top-level module
    # (a model importing another plugin's module, noop's LitNoop), not as a third-party package
    names = set()
    for path in paths:
        for entry in Path(path).iterdir():
            if entry.is_dir() or entry.suffix == ".py":
                names.add(entry.stem)
    return names


def analyse(modules: dict) -> list[PluginDeps]:
    """modules: category -> [(path, module)], as plugin_modules gives them"""
    local = local_modules({path for entries in modules.values() for path, _ in entries})
    distributions = metadata.packages_distributions()
    result = []
    for category, entries in modules.items():
        for path, module in entries:
            location = plugin_location(path, module)
            requirements_file = (location if location.is_dir() else location.parent) / REQUIREMENTS_FILE
            deps = PluginDeps(category, module, location, None)
            declared = set()
            if location.is_dir() and requirements_file.is_file():
                requirements, deps.errors = read_requirements(requirements_file)
                deps.requirements = [requirement_state(r) for r in requirements]
                declared = {canonicalize_name(r.name) for r in requirements}
            # an import not installed names no distribution (sklearn is scikit-learn): taken as declared
            # by a missing requirement, which is reported, and checked once installed
            some_missing = any(s.installed is None and s.applies for s in deps.requirements or [])
            for name, files in third_party(imported_names(location), local).items():
                providers = {canonicalize_name(d) for d in distributions.get(name, [])}
                if providers & declared or (not providers and (canonicalize_name(name) in declared or some_missing)):
                    continue
                deps.undeclared[name] = files
            result.append(deps)
    return result
