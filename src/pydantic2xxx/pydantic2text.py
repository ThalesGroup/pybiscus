from pydantic import BaseModel
from pydantic.fields import PydanticUndefined
from typing import Union, Literal
from enum import Enum
import inspect
from heredoc import get_basemodel_attribute_description

def text_label( label: str, is_config: bool = False, pybiscus_info: str = '' ):

    if label == "":
        return "<<<<Empty>>>>"
    return f'{label}: '

def generate_field_text(field_name: str, field_type, field_required: bool, field_default, field_description, inFieldSet: bool, prefix: str) -> str:

    field_text = ''
    opt_value = '' if field_default     is PydanticUndefined else field_default

    prefixed_name = prefix+field_name

    # Generate the text according to the type
    if field_type in { str, int, float }:
        field_text += text_label( prefixed_name, True )
        field_text += f'{opt_value}\n'

    elif field_type is bool:
        
        field_text += text_label( prefixed_name, True )
        field_text += f'{field_default}\n'

    elif inspect.isclass(field_type) and issubclass(field_type, Enum):
        
        field_text += text_label( prefixed_name, True )
        field_text += f'{opt_value}\n'
        
    elif field_type is type(None):
        field_text += f'{prefix}NONE'
        field_text +='\n'

    elif hasattr(field_type, '__origin__'):

        if field_type.__origin__ is list:

            # ### list ###
            field_text += text_label( prefixed_name, True )
            field_text += f'{opt_value}\n'

        elif field_type.__origin__ is dict:

            # ### dict ###
            pass

        elif field_type.__origin__ is Union:

            # ### Union ###
            
            is_option = (len(field_type.__args__) == 2 and field_type.__args__[1] is type(None))

            # default is the first
            active_index = 1
            propagate_default = False

            # if there is a default, check type
            if field_default is not PydanticUndefined:
                field_default_type = type( field_default )
                for index, sub_type in enumerate( field_type.__args__, 1 ):
                    if sub_type is field_default_type:
                        active_index = index
                        propagate_default = True
                        break

            if is_option:
                field_text += f'\n{prefix}# optional begin\n'
            else:
                field_text += f'\n{prefix}# union begin\n'


            first_sub_type = field_type.__args__[0]

            if is_option and first_sub_type in {str}:

                field_text += f"{prefix}{field_name}: {field_default}\n"

            else:
                field_text += f"{prefix}{field_name}:\n"

                for index, sub_type in enumerate( field_type.__args__, 1 ):

                    if not is_option:
                        if index == active_index:
                            field_text += f'{prefix}# default\n'
                        else:
                            field_text += f'{prefix}# unselected\n'

                    if propagate_default and index == active_index:
                        sub_field_default = field_default 
                    else:
                        sub_field_default = PydanticUndefined

                    field_text += generate_field_text(
                                    field_name        = str(sub_type), 
                                    field_type        = sub_type, 
                                    field_required    = False, 
                                    field_default     = sub_field_default, 
                                    field_description = PydanticUndefined,
                                    inFieldSet        = False,
                                    prefix            = f"{prefix}",
                                    )

                    if is_option and index == active_index:
                        break

            if is_option:
                field_text += f'{prefix}# optional end\n\n'
            else:
                field_text += f'{prefix}# union end\n\n'

        elif field_type.__origin__ is Literal:

            # ### Literal ###
            field_text += text_label( prefixed_name, True )
            field_text += f'{field_type.__args__[0]}\n'

        else:

            # ### ??? ###
            field_text += text_label( 'Field Type not handled !!!' )
            field_text += text_label( prefixed_name )

    elif issubclass(field_type, BaseModel):

        field_text += generate_model_text(field_type, prefix )

    else:

        field_text += f'  <???>{field_name}:   [{type(field_type).__qualname__}]:{(field_type).__qualname__}]</???>\n'

    return field_text


def generate_model_text(model: BaseModel, prefix: str ) -> str:

    if prefix is None:
        prefix = ""
        nextPrefix = ""
    else:
        nextPrefix = f"   {prefix}"

    model_text = f"{prefix}# class: {model.__name__}\n"

    if hasattr(model, "PYBISCUS_CONFIG"):
        
        pybiscus_config = model.PYBISCUS_CONFIG
        model_text += f'{prefix}{pybiscus_config}:\n'

    for field_name, field_info in model.model_fields.items():

        model_text += generate_field_text(
                                    field_name        = field_name, 
                                    field_type        = field_info.annotation,
                                    field_required    = field_info.is_required(), 
                                    field_default     = field_info.default, 
                                    #field_description = field_info.description,
                                    field_description = get_basemodel_attribute_description(model,field_name),
                                    inFieldSet        = True,
                                    prefix            = nextPrefix,
                                    )
   
    return model_text


