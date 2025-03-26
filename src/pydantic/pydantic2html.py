
from pydantic import BaseModel, Field
from pydantic.fields import PydanticUndefined
from typing import Union, Literal
from enum import Enum
import sys
import inspect

from src.flower.server_fabric import ConfigServer
from src.flower.client_fabric import ConfigClient

"""
// Trouver le parent contenant l'attribut data-toto
let parent = enfant.closest("div[data-toto]");

// Vérifier si data-toto est égal à "titi"
if (parent && parent.dataset.toto === "titi") {
    console.log("La valeur de data-toto est 'titi'");
} else {
    console.log("La valeur de data-toto n'est pas 'titi'");
}

"""

class PydanticToHtml:

    valid_status   = 'data-pybiscus-status="valid"'
    ignored_status = 'data-pybiscus-status="ignored"'

    @staticmethod
    def genProlog() -> str:

        return """

<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Typer2Html</title>

    <style>

        .fieldset-container {
            display: flex;
            flex-direction: row;
            gap: 10px;
        }

        .tab-container {
            width: 100%;
            border-bottom: 1px solid #ccc;
        }
        .tab-buttons {
            display: flex;
            border-bottom: 1px solid #ccc;
        }
        .tab-button {:
            padding: 10px 20px;
            cursor: pointer;
            border: 1px solid #ccc;
            border-bottom: none;
            margin-right: 5px;
        }
        .tab-button.active___ {
            background-color: #e0e0e0;
        }
        .tab-content {
            padding: 20px;
            border-top: 1px solid #ccc;
        }
        .tab-content:not(.active) {
            display: none;
        }

        .pybiscus-config {
            background-color: gray;
            color: orange;
            border: 1px solid orange;
            padding: 5px;
        }

        [data-pybiscus-status="ignored"] {
            background-color: #f0f0f0; /* Gris clair */
        }

        [data-pybiscus-status="valid"] {
            background-color: #e0f7fa; /* Bleu très clair */
        }

    </style>
</head>

<body>
    <div id="top-div" data-pybiscus-status="valid">
    """

    @staticmethod
    def genEpilog() -> str:

        return """
      </div>

    <button id="select-button">Sélectionner et Appeler fff</button>

<script>
    document.querySelectorAll('.tab-container').forEach(container => {
        container.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', () => {

                // desactivate all tabs of the container
                
                container.querySelectorAll('.tab-button').forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('data-pybiscus-status', 'ignored');
                    } );
                container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                // activate the clicked tab and its associated content

                button.classList.add('active');
                button.setAttribute('data-pybiscus-status', 'valid');

                associatedDiv = container.querySelector(`#${button.dataset.tab}`);
                associatedDiv.classList.add('active');
                associatedDiv.setAttribute('data-pybiscus-status', 'valid');
            });
        });
    });

    const radioButtons = document.querySelectorAll('input[type="radio"].pybiscus_radiobutton');

    // Ajoute un écouteur d'événement pour chaque input radio
    radioButtons.forEach(function(radio) {

        radio.addEventListener('change', function() {
            
            const radiosWithSameName = document.querySelectorAll(`input[type="radio"][name="${radio.name}"]`);

            // Itère sur chaque bouton radio avec le même nom
            radiosWithSameName.forEach(function(radioButton) {

                const parentDiv = radioButton.parentElement;
                parentDiv.setAttribute('data-pybiscus-status', 'ignored');
            });

            // Sélectionne le div parent de l'input radio
            const parentDiv = radio.parentElement;
            parentDiv.setAttribute('data-pybiscus-status', 'valid');
        });

        // Initialise l'état au chargement de la page
        if (radio.checked) {
            radio.parentElement.setAttribute('data-pybiscus-status', 'valid');
        } else {
            radio.parentElement.setAttribute('data-pybiscus-status', 'ignored');
        }
    });

    function traverseDOM(element) {

        if (element.getAttribute('data-pybiscus-status') === 'ignored') {

        } else {

            if (element.hasAttribute('data-pybiscus-name')) {

                const attributeValue = element.getAttribute('data-pybiscus-name');
                console.log( attributeValue + " = " + element.value );

            } else {

                const children = element.children;
                for (let i = 0; i < children.length; i++) {
                    traverseDOM(children[i]);
                }
            }
        }
    }

    const button = document.getElementById('select-button');

    // Ajoute un écouteur d'événement pour le clic sur le bouton
    button.addEventListener('click', function() {

        // Sélectionne l'élément avec l'ID top-div
        const topDiv = document.getElementById('top-div');

        // Appelle la fonction fff en passant l'élément en paramètre
        traverseDOM(topDiv);
    });

</script>

</body>
</html>
"""

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

#_field_input_type = {
        #str: "text",
        #int: "number"
    #}

def generate_field_html(field_name: str, field_type, field_required: bool, field_default, field_description, inFieldSet: bool, prefix: str) -> str:

    """
    sys.stderr.write(f"{field_name}, {field_type}, {field_required}, {field_default}, {field_description}, {inFieldSet}\n")

    if inspect.isclass(field_type):
        sys.stderr.write(f"YES {field_type}, {type(field_type)}, {issubclass(field_type,Enum)}\n")
    else:
        sys.stderr.write(f"NO {field_type}, {type(field_type)}\n")
        """

    field_html = ''
    opt_title = '' if field_description is None else f' title="{field_description}" '
    opt_value = '' if field_default     is PydanticUndefined else f' value="{field_default}" '
    opt_required = "required" if field_required else ""
    pybiscus_marker = f' data-pybiscus-name="{prefix+field_name}" '

    # Générer le champ HTML en fonction du type
    if field_type is str:
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

                for i in range(default_list_len):  
                    field_html += f'  <input type="number" name="{field_name}_{i}" placeholder="integer">\n'
            elif field_type.__args__[0] is str:
                field_html += html_label( field_name, True )

                for i in range(default_list_len):  
                    field_html += f'  <input type="text" name="{field_name}_{i}" placeholder="string">\n'
            field_html += f'  <br>\n'

        elif field_type.__origin__ is dict:

            # ### dict ###
            
            key_type, value_type = field_type.__args__
            field_html += html_label( field_name, True )
            
            for key in range(5):
                field_html += f'  <input type="text" id="{field_name}_key_{key}" name="{field_name}_key_{key}" placeholder="key_{key}">\n'
                field_html += f'  <input type="text" id="{field_name}_val_{key}" name="{field_name}_val_{key}" placeholder="value_{key}"><br>\n'

        elif field_type.__origin__ is Union:

            # ### Union ###
            
            field_html += '<fieldset class="fieldset-container">\n'
            field_html += f'  <legend><div class="pybiscus-config">{field_name}</div></legend>\n'
            prefix += f"{field_name}."

            if False:

                for index, sub_type in enumerate( field_type.__args__ ):

                    if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                        field_html += generate_model_html(sub_type, inFieldSet, prefix)
                    else:
                        field_html += '<fieldset>\n'
                        field_html += f'<legend>union_{index}</legend>\n'
                        field_html += generate_field_html("", sub_type, False, PydanticUndefined, True, prefix)
                        field_html += '</fieldset>\n'
            else:

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

                field_html += '''
<div class="tab-container">
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
                                    field_description = field_info.description,
                                    inFieldSet        = True,
                                    prefix            = prefix,
                                    )
   
    if inFieldSet:
        model_html += '</fieldset>\n'
    
    return model_html


def generate_model_form(model: BaseModel ) -> str:

    return PydanticToHtml.genProlog() + generate_model_html(model, True, "") + PydanticToHtml.genEpilog()

if __name__ == "__main__" :

    param = sys.argv[1] if len(sys.argv) == 2 else "all"
    
    if param != "server":
        form_html = generate_model_form(ConfigClient)
        print(form_html)
    if param != "client":
        form_html = generate_model_form(ConfigServer)
        print(form_html)
