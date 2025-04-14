import re
from pydantic import BaseModel

def get_basemodel_attribute_description(basemodel: BaseModel, attribute_name: str) -> str:
    """Access to the attribute description in the Model class docstring"""

    if hasattr(basemodel, '__doc__') :
        docstring = basemodel.__doc__
        if docstring:
            #print(attribute_name)
            pattern = rf"^.*{re.escape(attribute_name)}.*=\s*(.+)"
            match = re.search(pattern, docstring, re.MULTILINE)
            return match.group(1) if match else docstring

    return f"{basemodel.__name__}:{attribute_name}"
