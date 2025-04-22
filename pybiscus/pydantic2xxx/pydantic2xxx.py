import sys
from abc import ABC, abstractmethod
from typing import override
from pydantic import BaseModel
from enum import StrEnum

from pybiscus.flower.server_fabric import ConfigServer
from pybiscus.flower.client_fabric import ConfigClient

from pydantic2text import generate_model_text
from pydantic2html import generate_model_page
from pybiscus.core.pybiscusexception import PybiscusInternalException

class ModelGenerator(ABC):
    class Kind(StrEnum):
        HTML  = 'html'
        TEXT  = 'text'

    @abstractmethod
    def generate(self, model: BaseModel) -> str :
        pass


class HtmlModelGenerator(ModelGenerator):

    @override
    def generate(self, model: BaseModel) -> str :
        return generate_model_page(model,'pybiscus.session.node','node.html','check_exec_buttons')
    
class TextModelGenerator(ModelGenerator):

    @override
    def generate(self, model: BaseModel) -> str :
        return generate_model_text(model,None)


def generate_model_representation(model: BaseModel, generatorName: str) -> str:

    generator = None

    if generatorName == ModelGenerator.Kind.HTML.value:
        generator = HtmlModelGenerator()
    elif generatorName == ModelGenerator.Kind.TEXT.value:
        generator = TextModelGenerator()
    else:
        raise PybiscusInternalException(f"Bad model generator kind : {generatorName}")
    
    return generator.generate(model)

if __name__ == "__main__" :

    role = sys.argv[1] if len(sys.argv) >= 2 else "all"
    output = sys.argv[2] if len(sys.argv) == 3 else "html"

    # print(f"role : {role} output: {output}")    
    if role != "server":
        result = generate_model_representation(ConfigClient, output)
        print(result)
    if role != "client":
        result = generate_model_representation(ConfigServer, output)
        print(result)
