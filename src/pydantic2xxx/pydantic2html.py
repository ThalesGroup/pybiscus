from pydantic import BaseModel
from pydantic.fields import PydanticUndefined
from typing import Union, Literal
from enum import Enum
import inspect
import html
import importlib.resources

from src.pybiscusexception import PybiscusInternalException
from src.pydantic2xxx.heredoc import get_basemodel_attribute_description

class PydanticToHtml:

    valid_status   = 'data-pybiscus-status="valid"'
    ignored_status = 'data-pybiscus-status="ignored"'

def html_label( label: str, is_config: bool = False, pybiscus_info: str = '' ):

    if label == "":
        return ""
    if is_config:
        return f'  <label class="pybiscus-config" {pybiscus_info}>{label}</label>\n'
    else:
        return f'  <label {pybiscus_info}>{label}</label>\n'

def index_generator():
    counter = 1

    while True:
        nb = counter
        counter += 1
        yield nb

index_generator_instance = index_generator()

def new_index():
    return next(index_generator_instance)

def generate_tab_name(field_type, default) -> str:
    if field_type is str:
        return 'string'
    elif field_type is int:
        return 'integer'
    elif field_type is float:
        return 'float'
    elif field_type is bool:
        return 'bool'
    elif field_type is type(None):
        return 'None'
    elif hasattr(field_type, '__origin__'):
        if field_type.__origin__ is list:
            return f'list of {generate_tab_name(field_type.__args__[0], default)}'
        else:
            return default
    elif issubclass(field_type, BaseModel):

        if hasattr(field_type, "PYBISCUS_ALIAS"):

            return field_type.PYBISCUS_ALIAS
        else:
            return field_type.__name__
    else:
        return default

def generate_field_html(field_name: str, field_type, field_required: bool, field_default, field_description, inFieldSet: bool, prefix: str) -> str:

    field_html = ''
    opt_title = '' if (field_description is None or field_description is PydanticUndefined) else f' title="{html.escape(field_description)}" '
    opt_value = '' if field_default     is PydanticUndefined else f' value="{field_default}" '
    opt_required = "required" if field_required else ""

    prefixed_name = prefix+field_name
    if prefixed_name.endswith("."):
        prefixed_name = prefixed_name[:-1]
    pybiscus_marker = f' data-pybiscus-name="{prefixed_name}" '

    # generate HTML field according to type
    if field_type is str:
        opt_value = '' if (field_default is PydanticUndefined or field_default is None ) else f' value="{html.escape(field_default)}" '
        field_html += html_label( field_name, True )
        field_html += f'  <input type="text" {opt_title} {opt_value} placeholder="string" {opt_required} {pybiscus_marker}><br>\n'

    elif field_type is int:
        field_html += html_label( field_name, True )
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="integer" {opt_required} {pybiscus_marker}><br>\n'

    elif field_type is float:
        field_html += html_label( field_name, True )
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="float" {opt_required} step="0.001" {pybiscus_marker}><br>\n'

    elif field_type is bool:
        opt_checked = "checked" if True == field_default else ""
        
        field_html += html_label( field_name, True )
        field_html += f'  <input type="checkbox" id="{field_name}" name="{field_name}" {opt_title} {opt_value} {opt_checked} {pybiscus_marker}> <br>\n'

    elif inspect.isclass(field_type) and issubclass(field_type, Enum):
        
        field_html += '<fieldset class="fieldset-container">\n'
        field_html += f'  <legend><div class="pybiscus-config">{field_name}</div></legend>\n'

        option_name= f"option-{new_index()}"

        for member in field_type:

            if member.value == field_default:
                opt_checked = "checked" 
                status = PydanticToHtml.valid_status
            else:
                opt_checked = "" 
                status = PydanticToHtml.ignored_status

            field_html += f'''
<div>
    <input type="radio" name="{option_name}" {opt_title} value="{member.value}" {opt_checked} {pybiscus_marker} class="pybiscus_radiobutton"><label>{member.value}</label>
</div>
'''

        field_html += '</fieldset>\n'
        
    elif field_type is type(None):
        field_html += html_label( 'NONE' )

    elif hasattr(field_type, '__origin__'):

        if field_type.__origin__ is list:

            # ### list ###
            
            default_list_len = 5

            if field_type.__args__[0] is int:
                field_html += html_label( field_name, True )

                #for i in range(default_list_len):  
                #    field_html += f'  <input type="number" name="{field_name}_{i}" placeholder="integer">\n'

                field_html += f'  <input type="text" {opt_title} {opt_value} placeholder="comma separated int list" {pybiscus_marker}><br>\n'

            elif field_type.__args__[0] is str:
                field_html += html_label( field_name, True )

                #for i in range(default_list_len):  
                for i in range(0):  
                    field_html += f'  <input type="text" name="{field_name}_{i}" placeholder="string">\n'
            field_html += f'  <br>\n'

        elif field_type.__origin__ is dict:

            # ### dict ###
            
            key_type, value_type = field_type.__args__
            field_html += html_label( field_name, True )
            
            if field_default is None or field_default is PydanticUndefined:
                items = []
            else:
                items = list(field_default.items())

            for index in range(1):

                if len(items) > index:
                    key, value = items[index]
                    opt_key   = f' value="{key}" '
                    opt_value = f' value="{value}" '
                else:
                    opt_key   = ''
                    opt_value = ''

                field_html += html_label( "key" )
                field_html += f'  <input type="text" id="{field_name}_key_{index}" name="{field_name}_key_{index}" placeholder="key_{index}" {opt_key}>\n'
                field_html += html_label( "value" )
                field_html += f'  <input type="text" id="{field_name}_val_{index}" name="{field_name}_val_{index}" placeholder="value_{index}" {opt_value}><br>\n'

        elif field_type.__origin__ is Union:

            # ### Union ###
            
            field_html += '<fieldset class="fieldset-container">\n'
            field_html += f'  <legend><div class="pybiscus-config">{field_name}</div></legend>\n'
            prefix += f"{field_name}."

            tab_nb = new_index()

            # determine the active tab index

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

            field_html += '''   <div class="tab-container">
    <div class="tab-buttons">
'''

            # tab generation
            for index, sub_type in enumerate( field_type.__args__, 1 ):

                if index == active_index:
                    active = 'active'
                    status = PydanticToHtml.valid_status
                else:
                    active = ''
                    status = PydanticToHtml.ignored_status

                tab_name = generate_tab_name( sub_type, f'Tab {index}' )
                field_html += f'        <div class="tab-button {active}" data-tab="tab{tab_nb}-{index}" {status}>{tab_name}</div>\n'
            field_html += "    </div>\n"

            # tab content generation
            for index, sub_type in enumerate( field_type.__args__, 1 ):

                if index == active_index:
                    active = 'active'
                    status = 'data-pybiscus-status="valid"'
                else:
                    active = ''
                    status = 'data-pybiscus-status="ignored"'

                field_html += f'<div id="tab{tab_nb}-{index}" class="tab-content {active}" {status}>\n' 

                if propagate_default and index == active_index:
                    sub_field_default = field_default 
                else:
                    sub_field_default = PydanticUndefined

                field_html += generate_field_html(
                                field_name        = "", 
                                field_type        = sub_type, 
                                field_required    = False, 
                                field_default     = sub_field_default, 
                                field_description = PydanticUndefined,
                                inFieldSet        = False,
                                prefix            = prefix,
                                )
                field_html += '</div>\n'
            field_html += "</div>\n"

            field_html += '</fieldset>\n'

        elif field_type.__origin__ is Literal:

            # ### Literal ###
            field_html += html_label( field_name, True )
            field_html += f'<input type="text" value="{field_type.__args__[0]}" {pybiscus_marker} readonly><br>\n'

        else:

            # ### ??? ###
            field_html += html_label( 'Field Type not handled !!!' )
            field_html += html_label( field_name )

    elif issubclass(field_type, BaseModel):

        field_html += generate_model_html(field_type, inFieldSet, prefix )

    else:
        field_html += f' ????<br>\n'

        field_html += f'  <label>{field_name}:   [{type(field_type).__qualname__}]:{(field_type).__qualname__}]</label>\n'
        field_html += f'  <br>\n'

    return field_html


def generate_model_html(model: BaseModel, inFieldSet: bool, prefix: str ) -> str:

    model_html = ''

    if inFieldSet:
        model_html += '<fieldset>\n'

        if hasattr(model, "PYBISCUS_CONFIG"):
            
            pybiscus_config = model.PYBISCUS_CONFIG
            model_html += f'<legend><div class="pybiscus-config">{pybiscus_config}</div></legend>\n'
            prefix += f"{pybiscus_config}."

        elif hasattr(model, "PYBISCUS_ALIAS"):

            pybiscus_alias = model.PYBISCUS_ALIAS
            model_html += f'<legend>{pybiscus_alias}</legend>\n'

        else:
            model_html += f'<legend>{model.__name__}</legend>\n'

    for field_name, field_info in model.model_fields.items():

        model_html += generate_field_html(
                                    field_name        = field_name, 
                                    field_type        = field_info.annotation,
                                    field_required    = field_info.is_required(), 
                                    field_default     = field_info.default, 
                                    #field_description = field_info.description,
                                    field_description = get_basemodel_attribute_description(model,field_name),
                                    inFieldSet        = True,
                                    prefix            = prefix,
                                    )
   
    if inFieldSet:
        model_html += '</fieldset>\n'
    
    return model_html


def generate_model_page(model: BaseModel, templatePath: str, templateName: str ) -> str:

    modelName = model.__name__

    if modelName == "ConfigServer":
        action = "server"
    elif modelName == "ConfigClient":
        action = "client"
    else:
        action = "unknown"

    try:
        with importlib.resources.files(templatePath).joinpath(templateName).open('r') as file:
            html_template = file.read()
        body = generate_model_html(model, True, "")
        html = html_template.replace( "MODEL_NAME", modelName ).replace( "ACTION", action ).replace( "BODY", body )
    except FileNotFoundError:
        raise PybiscusInternalException("Template file pydantic.html not found !")
    except Exception as e:
        raise PybiscusInternalException(f"Html generation error ! {e}")

    return html
