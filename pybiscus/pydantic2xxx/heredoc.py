import inspect
import re
from typing import Optional

from pydantic import BaseModel

def get_basemodel_attribute_description(basemodel: BaseModel, attribute_name: str) -> Optional[str]:
    """the field's Field(description=...), else its "name ... = description" line of the class
    docstring with the more indented lines that continue it; None without either"""

    field = getattr(basemodel, "model_fields", {}).get(attribute_name)
    if field is not None and field.description:
        return field.description

    # the class's own docstring: an undocumented subclass would show its parent's
    docstring = basemodel.__dict__.get("__doc__")
    if not docstring:
        return None

    lines = inspect.cleandoc(docstring).splitlines()
    # "name ... = description" up to the first "=" ("clients_fit_local_epochs = ... (>= 1)" was cut at
    # the last one), or numpy's "name:" with the description below; the first line wins, so that
    # code quoted further down the docstring ("accelerator: ... = "auto",") is not taken for it
    name = re.escape(attribute_name)
    patterns = (re.compile(rf"^(\s*){name}\b[^=\n]*=\s*(.*)$"), re.compile(rf"^(\s*){name}\s*:\s*(.*)$"))
    for number, line in enumerate(lines):
        match = next((m for m in (pattern.match(line) for pattern in patterns) if m), None)
        if match is None:
            continue
        indent = len(match.group(1))
        parts = [match.group(2)]
        for following in lines[number + 1:]:
            if not following.strip() or len(following) - len(following.lstrip()) <= indent:
                break
            parts.append(following.strip())
        return " ".join(part for part in parts if part) or None

    return None
