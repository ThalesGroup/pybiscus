from pathlib import Path
from typing import Literal, NamedTuple, Optional

from pydantic import BaseModel, Field

import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.ensure_filesystem import ensure_dir_exists

# markers of the values known at run time only: every plugin uses the same ones, so that two
# templates are compared as plain strings
TAG, ROUND, CID = "{tag}", "{round}", "{cid}"

# the core's own reports, beside the plugins'
SERVER_LOG_FILE = "server_logs.txt"
METRICS_FILE = "metrics.txt"
CLIENT_CONFIGS_DIR = "config_clients"


class ReportingOutput(NamedTuple):
    parts: tuple
    # a directory belongs to its writer as a whole (TensorBoard's, for instance)
    kind: Literal["file", "dir"] = "file"


def output_file(*parts: str) -> ReportingOutput:
    return ReportingOutput(parts, "file")


def output_dir(*parts: str) -> ReportingOutput:
    return ReportingOutput(parts, "dir")


def template_of(output: ReportingOutput, tag: Optional[str]) -> str:
    """the path relative to the reporting directory, the run time values as markers"""
    parts = [tag if part == TAG else part for part in output.parts if part != TAG or tag]
    return "/".join(segment for part in parts for segment in str(part).split("/") if segment not in ("", "."))


# path -> the config that writes it, for the paths no check could foresee
_claims: dict = {}


class ReportingOutputs(BaseModel):
    """a plugin's config that writes into the reporting directory: it declares its outputs, from
    which its paths are built and the server's check finds two writers of the same file"""

    def reporting_outputs(self) -> dict[str, ReportingOutput]:
        return {}

    def output_templates(self) -> list[tuple[str, str]]:
        """(template, kind) of every output"""
        tag = getattr(self, "tag", None)
        return [(template_of(output, tag), output.kind) for output in self.reporting_outputs().values()]

    def output_path(self, name: str, **values) -> Path:
        """the path of an output, its directory created; values: round, cid"""
        import pybiscus.core.pybiscuscontext as pcpc
        output = self.reporting_outputs()[name]
        relative = template_of(output, getattr(self, "tag", None))
        for marker, value in values.items():
            relative = relative.replace("{" + marker + "}", str(value))
        path = pcpc.pybiscus_context[pcpc.REPORTING_PATH] / relative
        owner = _claims.setdefault(path, self)
        if owner is not self:
            logm.console.log(f"⚠️ reports: {path} written by both {type(owner).__name__} and {type(self).__name__}")
        ensure_dir_exists(path if output.kind == "dir" else path.parent)
        return path


class TaggedReportingOutputs(ReportingOutputs):

    tag: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", description=
        "subdirectory of this instance's files; needed when the plugin appears more than once, "
        "to save before and after a transformation for instance")


def collisions(outputs: list[tuple[str, str, str]]) -> list[str]:
    """outputs: (writer, template, kind); two writers of one file, or a file in another's directory"""
    problems = []
    for index, (writer, template, kind) in enumerate(outputs):
        for other_writer, other_template, other_kind in outputs[index + 1:]:
            if template == other_template:
                problems.append(f"{writer} and {other_writer} both write {template}")
            elif kind == "dir" and other_template.startswith(template + "/"):
                problems.append(f"{other_writer} writes {other_template} in the directory {template} of {writer}")
            elif other_kind == "dir" and template.startswith(other_template + "/"):
                problems.append(f"{writer} writes {template} in the directory {other_template} of {other_writer}")
    return problems


def declared_outputs(node, label: str = "") -> list[tuple[str, str, str]]:
    """(writer, template, kind) of every config under node that declares outputs; writer: its
    place in the configuration, with its plugin's name"""
    found = []
    if isinstance(node, ReportingOutputs):
        found += [(label, template, kind) for template, kind in node.output_templates()]
    if isinstance(node, BaseModel):
        for field in type(node).model_fields:
            child = getattr(node, field)
            # a plugin's block is {name, config}: its name says which plugin writes
            name = getattr(child, "name", None)
            # the config of a named block is the plugin itself: ".config" says nothing more
            child_label = label if field == "config" and isinstance(getattr(node, "name", None), str) \
                else f"{label}.{field}" if label else field
            if isinstance(name, str) and not isinstance(child, ReportingOutputs):
                child_label += f" ({name})"
            found += declared_outputs(child, child_label)
    elif isinstance(node, (list, tuple)):
        for index, child in enumerate(node):
            name = getattr(child, "name", None)
            found += declared_outputs(child, f"{label}[{index}]" + (f" ({name})" if isinstance(name, str) else ""))
    elif isinstance(node, dict):
        for key, child in node.items():
            found += declared_outputs(child, f"{label}.{key}")
    return found
