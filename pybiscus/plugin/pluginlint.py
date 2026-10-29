import ast
import inspect
import re
import sys
import textwrap
from enum import Enum
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin, is_typeddict

from pydantic import BaseModel

from pybiscus.plugin.plugindeps import plugin_location

ERROR, WARNING = "error", "warning"

# rule -> (severity, what it asks)
RULES = {
    "import": (ERROR, "the plugin imports and declares its (class, config) pairs: the other rules read them"),
    "interface": (ERROR, "each class it registers implements the interface of its category (a model a LightningModule...): the loader skips it otherwise"),
    "manifest": (ERROR, "a plugin package beside the manifest's modules is listed in it"),
    "print": (ERROR, "no print: pybiscus.core.pybiscus_logger, so that the output reaches the session's pages"),
    "extra-forbid": (ERROR, "each configuration model refuses unknown fields: model_config = ConfigDict(extra=\"forbid\")"),
    "description": (ERROR, "each configuration field has a description, shown by the forms and the reference"),
    "alias": (WARNING, "the configuration has a PYBISCUS_ALIAS, the label of the forms (its name otherwise)"),
    "group": (ERROR, "a strategy or a strategy decorator has a PYBISCUS_GROUP, its family in the forms"),
    "strategy": (ERROR, "a strategy derives from FlowerStrategyFactory; an aggregate_fit it overrides calls super().aggregate_fit"),
    "data-sections": (ERROR, "a data configuration is in train / val / test sections"),
    "reporting-outputs": (ERROR, "a plugin writing into the reporting directory declares its outputs (ReportingOutputs)"),
    "model-signature": (ERROR, "a model exposes signature (or signatures(mode)), a TypedDict with a loss key: the keys the training and test loops average and report"),
    "model-hyperparameters": (WARNING, "a model's hyperparameters are plain values: a session imposes only those on every form and lower level (a list, a dict or a section is left to each)"),
}

IGNORE = re.compile(r"#\s*pybiscus-lint:\s*ignore=([\w,-]+)")

# the fields every plugin configuration has, described by the family itself
FAMILY_FIELDS = {"name", "config", "empty_configuration"}

DATA_SECTIONS = ("train", "val", "test")

SCALARS = (str, int, float, bool, type(None))


@dataclass
class Finding:
    rule: str
    file: Path
    line: int
    message: str

    @property
    def severity(self) -> str:
        return RULES[self.rule][0]


@lru_cache(maxsize=None)
def parsed(file: Path):
    text = file.read_text(encoding="utf-8", errors="replace")
    try:
        return ast.parse(text), text.splitlines()
    except SyntaxError:
        return None, text.splitlines()


def ignored(finding: Finding) -> bool:
    _, lines = parsed(finding.file)
    if not 0 < finding.line <= len(lines):
        return False
    match = IGNORE.search(lines[finding.line - 1])
    return bool(match) and finding.rule in match.group(1).split(",")


def sources(location: Path) -> list[Path]:
    return sorted(p for p in location.rglob("*.py") if "__pycache__" not in p.parts) if location.is_dir() else [location]


def inside(cls, location: Path) -> bool:
    try:
        return Path(inspect.getsourcefile(cls)).resolve().is_relative_to(location.resolve())
    except (TypeError, OSError):
        return False


def class_place(cls) -> tuple[Path, int, ast.ClassDef | None]:
    file = Path(inspect.getsourcefile(cls))
    tree, _ = parsed(file)
    for node in ast.walk(tree) if tree else ():
        if isinstance(node, ast.ClassDef) and node.name == cls.__name__:
            return file, node.lineno, node
    return file, 1, None


def field_line(cls, name: str) -> int:
    _, line, node = class_place(cls)
    for statement in node.body if node else ():
        if isinstance(statement, ast.AnnAssign) and getattr(statement.target, "id", None) == name:
            return statement.lineno
    return line


def nested_models(annotation):
    origin = get_origin(annotation)
    if origin is Annotated:
        yield from nested_models(get_args(annotation)[0])
    elif origin is Literal:
        return
    elif origin is not None:
        for arg in get_args(annotation):
            yield from nested_models(arg)
    elif inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        yield annotation


def own_models(configs, location: Path) -> list[type[BaseModel]]:
    """the configuration models the plugin defines, reached from its configurations; a section of
    the core (datasplit's partition) or of another plugin is checked there"""
    seen, order, todo = set(), [], list(configs)
    while todo:
        model = todo.pop(0)
        if model in seen:
            continue
        seen.add(model)
        if inside(model, location):
            order.append(model)
        for field in model.model_fields.values():
            todo += nested_models(field.annotation)
    return order


def defining_class(model, name: str):
    return next((c for c in model.__mro__ if name in c.__dict__.get("__annotations__", {})), model)


def config_rules(category: str, configs, implementations, location: Path) -> list[Finding]:
    from pybiscus.pydantic2xxx.heredoc import get_basemodel_attribute_description

    findings, undescribed = [], set()
    for model in own_models(configs, location):
        file, line, _ = class_place(model)
        if model.model_config.get("extra") != "forbid":
            findings.append(Finding("extra-forbid", file, line, f"{model.__name__} accepts unknown fields"))
        for name, field in model.model_fields.items():
            # an inherited field is reported once, where it is written
            owner = defining_class(model, name)
            if name in FAMILY_FIELDS or field.exclude or not inside(owner, location) or (owner, name) in undescribed:
                continue
            if not get_basemodel_attribute_description(model, name):
                undescribed.add((owner, name))
                findings.append(Finding("description", class_place(owner)[0], field_line(owner, name),
                                        f"{owner.__name__}.{name} has no description"))

    for config in configs:
        if not inside(config, location):
            continue
        file, line, _ = class_place(config)
        if not getattr(config, "PYBISCUS_ALIAS", None):
            findings.append(Finding("alias", file, line, f"{config.__name__} has no PYBISCUS_ALIAS"))
        if category in ("strategy", "strategydecorator") and not getattr(config, "PYBISCUS_GROUP", None):
            findings.append(Finding("group", file, line, f"{config.__name__} has no PYBISCUS_GROUP"))
        if category == "data":
            findings += data_rules(config, file, line)
        if category == "model":
            findings += model_rules(config, location)

    if category == "strategy":
        findings += strategy_rules(implementations, location)
    return findings


def is_scalar(annotation) -> bool:
    origin = get_origin(annotation)
    if origin is Annotated:
        return is_scalar(get_args(annotation)[0])
    if origin is Literal:
        return True
    if origin in (Union, UnionType):
        # Optional[int], int | str: plain if every member is
        return all(is_scalar(arg) for arg in get_args(annotation))
    if origin is not None:
        return False
    return annotation in SCALARS or (inspect.isclass(annotation) and issubclass(annotation, (Enum, *SCALARS)))


def model_rules(config, location: Path) -> list[Finding]:
    inner = next(nested_models(config.model_fields["config"].annotation), None) if "config" in config.model_fields else None
    if inner is None:
        return []
    findings = []
    for name, field in inner.model_fields.items():
        owner = defining_class(inner, name)
        if name in FAMILY_FIELDS or not inside(owner, location) or is_scalar(field.annotation):
            continue
        findings.append(Finding("model-hyperparameters", class_place(owner)[0], field_line(owner, name),
                                f"{owner.__name__}.{name} is not a plain value: a session leaves it to each form and lower level"))
    return findings


def data_rules(config, file: Path, line: int) -> list[Finding]:
    inner = next(nested_models(config.model_fields["config"].annotation), None) if "config" in config.model_fields else None
    if inner is None:
        return [Finding("data-sections", file, line, f"{config.__name__} has no config section")]
    missing = [s for s in DATA_SECTIONS
               if s not in inner.model_fields or next(nested_models(inner.model_fields[s].annotation), None) is None]
    if not missing:
        return []
    inner_file, inner_line, _ = class_place(inner)
    return [Finding("data-sections", inner_file, inner_line, f"{inner.__name__} has no {' / '.join(missing)} section")]


def calls_super(function: ast.FunctionDef, name: str) -> bool:
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == name
               and isinstance(node.func.value, ast.Call) and getattr(node.func.value.func, "id", None) == "super"
               for node in ast.walk(function))


def strategy_rules(implementations, location: Path) -> list[Finding]:
    from pybiscus.flower.flowerstrategy import FlowerStrategyFactory

    findings = []
    for factory in implementations:
        if not inside(factory, location):
            continue
        file, line, _ = class_place(factory)
        if not issubclass(factory, FlowerStrategyFactory):
            findings.append(Finding("strategy", file, line, f"{factory.__name__} does not derive from FlowerStrategyFactory"))
            continue
        for cls in inspect.getmro(factory.flower_strategy_class or object):
            if "aggregate_fit" not in cls.__dict__ or not inside(cls, location):
                continue
            cls_file, _, node = class_place(cls)
            method = next((s for s in node.body if isinstance(s, ast.FunctionDef) and s.name == "aggregate_fit"), None) if node else None
            if method is not None and not calls_super(method, "aggregate_fit"):
                findings.append(Finding("strategy", cls_file, method.lineno,
                                        f"{cls.__name__}.aggregate_fit does not call super().aggregate_fit (Flower's checks and metrics)"))
    return findings


def conforms(cls, category: str) -> bool:
    from pybiscus.plugin.families import FAMILY_INTERFACES, family_interface

    return category not in FAMILY_INTERFACES or (inspect.isclass(cls) and issubclass(cls, family_interface(category)))


def interface_rules(category: str, implementations, location: Path, init: Path) -> list[Finding]:
    from pybiscus.plugin.families import family_interface

    findings = []
    for cls in implementations:
        if conforms(cls, category):
            continue
        file, line = class_place(cls)[:2] if inspect.isclass(cls) and inside(cls, location) else (init, 1)
        findings.append(Finding("interface", file, line, f"{getattr(cls, '__name__', cls)!s} is not a "
                                f"{family_interface(category).__name__}, the interface of the {category} plugins"))
    return findings


def self_assigned(cls, attribute: str) -> list:
    """the module-level objects a method of cls (or of a base class) assigns to self.<attribute>"""
    values = []
    for klass in cls.__mro__:
        try:
            _, _, node = class_place(klass)
        except (TypeError, OSError):
            continue
        namespace = vars(sys.modules.get(klass.__module__, object))
        for statement in ast.walk(node) if node else ():
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Name) and any(
                    isinstance(t, ast.Attribute) and t.attr == attribute and getattr(t.value, "id", None) == "self"
                    for t in statement.targets) and statement.value.id in namespace:
                values.append(namespace[statement.value.id])
    return values


def returned_signatures(function, cls) -> list:
    """what the signature's code returns, as far as reading it tells: a module-level name, or an
    attribute of self assigned one; anything else is left unchecked"""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (TypeError, OSError, SyntaxError):
        return []
    values = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Return) and node.value is not None):
            continue
        if isinstance(node.value, ast.Name) and node.value.id in function.__globals__:
            values.append(function.__globals__[node.value.id])
        elif isinstance(node.value, ast.Attribute) and getattr(node.value.value, "id", None) == "self":
            values += self_assigned(cls, node.value.attr)
    return values


def model_signature_rules(implementations, location: Path) -> list[Finding]:
    findings = []
    for cls in implementations:
        if not inside(cls, location):
            continue
        # the loops' own choice (signature_of_mode): signatures(mode) when callable, else signature
        attribute = inspect.getattr_static(cls, "signatures", None)
        if not callable(attribute):
            attribute = inspect.getattr_static(cls, "signature", None)
        if attribute is None:
            file, line, _ = class_place(cls)
            findings.append(Finding("model-signature", file, line, f"{cls.__name__} has no signature: the loops fail on it"))
            continue
        function = attribute.fget if isinstance(attribute, property) else attribute
        if inspect.isfunction(function):
            candidates, file, line = returned_signatures(function, cls), Path(inspect.getsourcefile(function)), inspect.getsourcelines(function)[1]
        else:
            candidates, (file, line, _) = [function], class_place(cls)
        for signature in candidates:
            name = getattr(signature, "__name__", repr(signature))
            if not is_typeddict(signature):
                findings.append(Finding("model-signature", file, line, f"{cls.__name__}'s signature {name} is not a TypedDict"))
            elif "loss" not in signature.__required_keys__:
                findings.append(Finding("model-signature", file, line,
                                        f"{cls.__name__}'s signature {name} has no loss key: the loss is not reported"))
    return findings


def source_rules(location: Path, configs) -> list[Finding]:
    from pybiscus.core.reportingoutputs import ReportingOutputs

    findings, reporting = [], []
    for file in sources(location):
        tree, _ = parsed(file)
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                findings.append(Finding("print", file, node.lineno, "print()"))
            elif isinstance(node, (ast.Name, ast.Attribute, ast.arg)) and \
                    (getattr(node, "id", None) or getattr(node, "attr", None) or getattr(node, "arg", None)) in ("reporting_path", "REPORTING_PATH"):
                reporting.append((file, node.lineno))
    declares = any(issubclass(m, ReportingOutputs) for m in own_models(configs, location))
    if reporting and not declares:
        file, line = reporting[0]
        findings.append(Finding("reporting-outputs", file, line,
                                "reads the reporting directory, but no configuration derives from ReportingOutputs"))
    return findings


def declares_plugin(package: Path) -> int:
    """the line of get_modules_and_configs in the package's __init__.py, 0 without it"""
    init = package / "__init__.py"
    tree, _ = parsed(init) if init.is_file() else (None, [])
    return next((n.lineno for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "get_modules_and_configs"), 0) if tree else 0


def manifest_rules(modules: dict) -> list[Finding]:
    listed = {(Path(path).resolve(), module) for entries in modules.values() for path, module in entries}
    findings = []
    for directory in sorted({path for path, _ in listed}):
        for package in sorted(p for p in directory.iterdir() if p.is_dir()):
            line = declares_plugin(package)
            if line and (directory, package.name) not in listed:
                findings.append(Finding("manifest", package / "__init__.py", line,
                                        f"{package.name} declares a plugin but no manifest lists it"))
    return findings


def lint_plugin(category: str, path: str, module: str) -> list[Finding]:
    from pybiscus.plugin.pluginmanager import get_skipped_plugins, import_plugin
    from pybiscus.plugin.registryloader import registry_and_configs

    location = plugin_location(path, module)
    init = location / "__init__.py" if location.is_dir() else location
    try:
        imported = import_plugin(module)
        if imported is None:
            missing = next((d for _, m, d in get_skipped_plugins() if m == module), "?")
            return [Finding("import", init, 1, f"skipped: missing dependency '{missing}' (pybiscus plugins deps)")]
        registry, configs = registry_and_configs(imported.get_modules_and_configs(), module)
    except Exception as e:
        return [Finding("import", init, 1, f"{type(e).__name__}: {e}")]
    implementations = list(registry.values())
    # the other rules read classes of the expected interface: a stray object would fail them
    conforming = [cls for cls in implementations if conforms(cls, category)]
    findings = interface_rules(category, implementations, location, init) + config_rules(category, configs, conforming, location)
    if category == "model":
        findings += model_signature_rules(conforming, location)
    return findings + source_rules(location, configs)


def lint(modules: dict) -> list[Finding]:
    """modules: category -> [(path, module)], as plugin_modules gives them; the findings an
    ignore comment on their line does not silence"""
    findings = manifest_rules(modules)
    for category, entries in modules.items():
        for path, module in entries:
            findings += lint_plugin(category, path, module)
    return [f for f in findings if not ignored(f)]
