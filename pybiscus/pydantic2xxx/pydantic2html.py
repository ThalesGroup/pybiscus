from typing_extensions import Annotated
from pydantic import BaseModel
from pydantic.fields import PydanticUndefined
from typing import Optional, Union, Literal, get_args, get_origin
from enum import Enum

import inspect
import html
import importlib.resources

from pybiscus.core.pybiscusexception import PybiscusInternalException
from pybiscus.pydantic2xxx.heredoc import get_basemodel_attribute_description

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
        field_html += f'  <input type="text" {opt_title} {opt_value} placeholder="string" {opt_required} {pybiscus_marker}>\n'

    elif field_type is int:
        field_html += html_label( field_name, True )
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="integer" {opt_required} {pybiscus_marker}>\n'

    elif field_type is float:
        field_html += html_label( field_name, True )
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="float" {opt_required} step="0.001" {pybiscus_marker}>\n'

    elif field_type is bool:
        opt_checked = "checked" if True == field_default else ""
        
        field_html += html_label( field_name, True )
        field_html += f'  <input type="checkbox" id="{field_name}" name="{field_name}" {opt_title} {opt_value} {opt_checked} {pybiscus_marker}> \n'

    elif inspect.isclass(field_type) and issubclass(field_type, Enum):
        
        field_html += '<fieldset class="pybiscus-fieldset-container">\n'
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

                field_html += f'  <input type="text" {opt_title} {opt_value} placeholder="comma separated int list" {pybiscus_marker}>\n'

            elif field_type.__args__[0] is str:
                field_html += html_label( field_name, True )

                #for i in range(default_list_len):  
                for i in range(0):  
                    field_html += f'  <input type="text" name="{field_name}_{i}" placeholder="string">\n'
            field_html += f'  \n'

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
                field_html += f'  <input type="text" id="{field_name}_val_{index}" name="{field_name}_val_{index}" placeholder="value_{index}" {opt_value}>\n'

        elif get_origin(field_type) is Annotated or get_origin(field_type) is Union:

            # an Annotated field is handled as an Union of only one type
            # as is it simplified by python / typing

            if get_origin(field_type) is Annotated:

                # ### Annotated ###

                # consider the inner field_type
                field_type, *params = get_args(field_type)

            if get_origin(field_type) is not Union:

                is_an_union = False
                is_an_option = False

                # consider the inner field_type
                field_type = get_args(field_type)

            else:

                # ### Union ###

                is_an_union = True
            
                # ### Optional ###

                # Optional[Type] is encoded by pedantic as : Union(Type, NoneType)
                is_an_option = len(field_type.__args__) == 2 and field_type.__args__[1] is type(None)

            # determine the active tab index

            # default is the first
            active_index = 1
            propagate_default = False

            if is_an_union:
                # if there is a default, check type
                if field_default is not PydanticUndefined:
                    field_default_type = type( field_default )
                    for index, sub_type in enumerate( field_type.__args__, 1 ):
                        if sub_type is field_default_type:
                            active_index = index
                            propagate_default = True
                            break

            prefix += f"{field_name}."
            optional_fs_class = "pybiscus-option-fs" if is_an_option else ""
            field_html += f'<fieldset class="pybiscus-fieldset-container {optional_fs_class}" data-pybiscus-prefix="{prefix[:-1]}">\n'

            if field_name != "":
                field_html += f'  <legend><div class="pybiscus-config">{field_name}'
                if is_an_option:
                    opt_checked = "checked" if active_index == 1 else ""
                    field_html += f' ❓ <input type="checkbox" class="pybiscus-option-cb" {opt_checked} > '
                field_html += '</div></legend>\n'

            tab_nb = new_index()

            field_html += '''   <div class="pybiscus-tab-container">
    <div class="pybiscus-tab-buttons">
'''

            # tab generation

            if not is_an_union:

                index = 1
                active = 'active'
                status = PydanticToHtml.valid_status
                tab_name = generate_tab_name( sub_type, 'Annotated' )

                field_html += f'        <div class="pybiscus-tab-button {active}" data-tab="tab{tab_nb}-{index}" {status}>{tab_name}</div>\n'

            else:
                for index, sub_type in enumerate( field_type.__args__, 1 ):

                    if index == active_index:
                        active = 'active'
                        status = PydanticToHtml.valid_status
                    else:
                        active = ''
                        status = PydanticToHtml.ignored_status

                    if is_an_option:
                        # having different blank names is used when setting option value
                        # as they are displayed => nothing appears
                        # but we are able to address the union values by name
                        # ' ' stands for Some(x), '  ' for None
                        tab_name = ' ' * index
                    else:
                        tab_name = generate_tab_name( sub_type, f'Tab {index}' )

                    field_html += f'        <div class="pybiscus-tab-button {active}" data-tab="tab{tab_nb}-{index}" {status}>{tab_name}</div>\n'

            field_html += "    </div>\n"

            # tab content generation
            if not is_an_union:

                active = 'active'
                status = 'data-pybiscus-status="valid"'
                opt_first = "pybiscus-first-tab-content"
                if propagate_default:
                    sub_field_default = field_default 
                else:
                    sub_field_default = PydanticUndefined

                field_html += f'<div id="tab{tab_nb}-{index}" class="pybiscus-tab-content {active} {opt_first}" {status}>\n' 
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

            else:
                for index, sub_type in enumerate( field_type.__args__, 1 ):

                    if index == active_index:
                        active = 'active'
                        status = 'data-pybiscus-status="valid"'
                    else:
                        active = ''
                        status = 'data-pybiscus-status="ignored"'

                    opt_first = "" if index > 1 else "pybiscus-first-tab-content"

                    field_html += f'<div id="tab{tab_nb}-{index}" class="pybiscus-tab-content {active} {opt_first}" {status}>\n' 

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
            field_html += f'<input type="text" value="{field_type.__args__[0]}" {pybiscus_marker} readonly>\n'

        else:

            # ### ??? ###
            field_html += html_label( f'Field Type not handled !!! {field_type}' )
            field_html += html_label( field_name )

    elif issubclass(field_type, BaseModel):

        field_html += generate_model_html(field_type, inFieldSet, prefix )

    else:
        field_html += f' ????\n'

        field_html += f'  <label>{field_name}:   [{type(field_type).__qualname__}]:{(field_type).__qualname__}]</label>\n'
        field_html += f'  \n'

    field_html = f'<div class="pybiscus-field">\n{field_html}</div>\n'

    return field_html


def generate_model_html(model: BaseModel, inFieldSet: bool, prefix: str) -> str:

    model_html = '<br>'

    if inFieldSet:
        model_html += f'<fieldset>\n'

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
                                    field_description = get_basemodel_attribute_description(model,field_name),
                                    inFieldSet        = True,
                                    prefix            = prefix,
                                    )
   
    if inFieldSet:
        model_html += '</fieldset>\n'
    
    return model_html


def generate_model_page(model: BaseModel, templatePath: str, templateName: str, buttons_type: str, on_document_load_js: str = "" ) -> str:

    modelName = model.__name__

    if modelName == "ConfigServer":
        action = "server"
    elif modelName == "ConfigClient":
        action = "client"
    else:
        action = "unknown"

    try:
        with importlib.resources.files(templatePath).joinpath(templateName).open('r') as file:
            html = file.read()
        with importlib.resources.files("pybiscus.session.agent").joinpath("pybiscus.css").open('r') as file:
            css = file.read()
        with importlib.resources.files("pybiscus.session.agent").joinpath(f"{buttons_type}.html").open('r') as file:
            buttons_html = file.read()
        with importlib.resources.files("pybiscus.session.agent").joinpath(f"{buttons_type}.js").open('r') as file:
            buttons_js = file.read()

        body = generate_model_html(model, True, "")

        html = html.replace( "CSS", css )
        html = html.replace( "BODY", body )
        html = html.replace( "BUTTONS_HTML", buttons_html )
        html = html.replace( "BUTTONS_JS", buttons_js )
        html = html.replace( "ON_DOCUMENT_LOAD_JS", on_document_load_js )
        html = html.replace( "MODEL_NAME", modelName ).replace( "ACTION", action )

    except Exception as e:
        raise PybiscusInternalException(f"Html generation error ! {e}")

    return html
