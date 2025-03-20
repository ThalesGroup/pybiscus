
from pydantic import BaseModel, Field
from pydantic.fields import PydanticUndefined
from typing import Union, Literal
from enum import Enum
import sys
import inspect

from src.flower.server_fabric import ConfigServer
from src.flower.client_fabric import ConfigFabric, ConfigClient

"""
   annotation: type[Any] | None
    default: Any
    default_factory: Callable[[], Any] | Callable[[dict[str, Any]], Any] | None
    alias: str | None
    alias_priority: int | None
    validation_alias: str | AliasPath | AliasChoices | None
    serialization_alias: str | None
    title: str | None
    field_title_generator: Callable[[str, FieldInfo], str] | None
    description: str | None
    examples: list[Any] | None
    exclude: bool | None
    discriminator: str | types.Discriminator | None
    deprecated: Deprecated | str | bool | None
    json_schema_extra: JsonDict | Callable[[JsonDict], None] | None
    frozen: bool | None
    validate_default: bool | None
    repr: bool
    init: bool | None
    init_var: bool | None
    kw_only: bool | None
    metadata: list[Any]
"""

def dump( fi ):

    print( f"-------------------<br>")
    print( f"annotation {fi.annotation}<br>")
    print( f"default {fi.default}<br>")
    print( f"default_factory {fi.default_factory}<br>")
    print( f"alias {fi.alias}<br>")
    print( f"alias_priority {fi.alias_priority}<br>")
    print( f"validation_alias {fi.validation_alias}<br>")
    print( f"serialization_alias {fi.serialization_alias}<br>")
    print( f"title {fi.title}<br>")
    print( f"field_title_generator {fi.field_title_generator}<br>")
    print( f"description {fi.description}<br>")
    print( f"examples {fi.examples}<br>")
    print( f"exclude {fi.exclude}<br>")
    print( f"discriminator {fi.discriminator}<br>")
    print( f"deprecated {fi.deprecated}<br>")
    print( f"json_schema_extra {fi.json_schema_extra}<br>")
    print( f"frozen {fi.frozen}<br>")
    print( f"validate_default {fi.validate_default}<br>")
    print( f"repr {fi.repr}<br>")
    print( f"init {fi.init}<br>")
    print( f"init_var {fi.init_var}<br>")
    print( f"kw_only {fi.kw_only}<br>")
    print( f"metadata {fi.metadata}<br>")


class PydanticToHtml:
    pass






def html_label( label, pybiscus_info='' ):
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
        return field_type.__name__
    else:
        return default

#_field_input_type = {
        #str: "text",
        #int: "number"
    #}

def generate_field_html(field_name, field_type, field_required: bool, field_default, field_description, inFieldSet: bool = True) -> str:

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
    pybiscus_marker = f' data-pybiscus-name="{field_name}" '
    pybiscus_always = f' data-pybiscus-condition="always" '
    pybiscus_if_checked = f' data-pybiscus-condition="if-checked" '
    pybiscus_if_div_active = f' data-pybiscus-condition="if-div-checked" '

    # Générer le champ HTML en fonction du type
    if field_type is str:
        field_html += html_label( field_name )
        #field_html += f'  <input type="text" id="{field_name}" name="{field_name}" {opt_title} {opt_value} placeholder="string" {opt_required}><br>\n'
        field_html += f'  <input type="text" {opt_title} {opt_value} placeholder="string" {opt_required} {pybiscus_marker} {pybiscus_always}><br>\n'

    elif field_type is int:
        field_html += html_label( field_name )
        #field_html += f'  <input type="number" id="{field_name}" name="{field_name}" {opt_title} {opt_value} placeholder="integer" {opt_required} {pybiscus_marker}><br>\n'
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="integer" {opt_required} {pybiscus_marker} {pybiscus_always}><br>\n'

    elif field_type is float:
        field_html += html_label( field_name )
        #field_html += f'  <input type="number" id="{field_name}" name="{field_name}" {opt_title} {opt_value} placeholder="float" {opt_required} step="0.001" {pybiscus_marker}><br>\n'
        field_html += f'  <input type="number" {opt_title} {opt_value} placeholder="float" {opt_required} step="0.001" {pybiscus_marker} {pybiscus_always}><br>\n'

    elif field_type is bool:
        opt_checked = "checked" if True == field_default else ""
        
        field_html += html_label( field_name )
        field_html += f'  <input type="checkbox" id="{field_name}" name="{field_name}" {opt_title} {opt_value} {opt_checked} {pybiscus_marker} {pybiscus_always}> <br>\n'

    elif inspect.isclass(field_type) and issubclass(field_type, Enum):
        
        field_html += '<fieldset class="fieldset-container">\n'
        field_html += f'  <legend>{field_name}:</legend>\n'

        option_name= f"option-{new_index()}"

        for member in field_type:
            opt_checked = "checked" if member.value == field_default else ""
            #field_html += f'<input type="radio" id="option1" name="{option_name}" {opt_title} value="{member.value}" {opt_checked} ><label>{member.value}</label>\n'
            field_html += f'<input type="radio" name="{option_name}" {opt_title} value="{member.value}" {opt_checked} {pybiscus_marker} {pybiscus_if_checked}><label>{member.value}</label>\n'

        field_html += '</fieldset>\n'
        
    elif field_type is type(None):
        field_html += html_label( 'NONE' )

    elif hasattr(field_type, '__origin__'):

        if field_type.__origin__ is list:

            # ### list ###
            
            default_list_len = 5

            if field_type.__args__[0] is int:
                field_html += html_label( field_name )
                for i in range(default_list_len):  
                    field_html += f'  <input type="number" name="{field_name}_{i}" placeholder="integer">\n'
            elif field_type.__args__[0] is str:
                field_html += html_label( field_name )
                for i in range(default_list_len):  
                    field_html += f'  <input type="text" name="{field_name}_{i}" placeholder="string">\n'
            field_html += f'  <br>\n'

        elif field_type.__origin__ is dict:

            # ### dict ###
            
            key_type, value_type = field_type.__args__
            field_html += html_label( field_name )
            
            for key in range(5):
                field_html += f'  <input type="text" id="{field_name}_key_{key}" name="{field_name}_key_{key}" placeholder="key_{key}">\n'
                field_html += f'  <input type="text" id="{field_name}_val_{key}" name="{field_name}_val_{key}" placeholder="value_{key}"><br>\n'

        elif field_type.__origin__ is Union:

            # ### Union ###
            
            field_html += '<fieldset class="fieldset-container">\n'
            field_html += f'  <legend>{field_name}:</legend>\n'

            if False:

                for index, sub_type in enumerate( field_type.__args__ ):

                    if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                        field_html += generate_model_html(sub_type, inFieldSet)
                    else:
                        field_html += '<fieldset>\n'
                        field_html += f'<legend>union_{index}</legend>\n'
                        field_html += generate_field_html("", sub_type, False, PydanticUndefined)
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
                    active = 'active' if index == active_index else ''
                    tab_name = generate_tab_name( sub_type, f'Tab {index}' )
                    field_html += f'        <div class="tab-button {active}" data-tab="tab{tab_nb}-{index}">{tab_name}</div>\n'
                field_html += "    </div>\n"

                # tab content generation
                for index, sub_type in enumerate( field_type.__args__, 1 ):
                    active = 'active' if index == active_index else ''
                    field_html += f'<div id="tab{tab_nb}-{index}" class="tab-content {active}">\n' 
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
                                    inFieldSet        = False
                                    )
                    field_html += '</div>\n'
                field_html += "</div>\n"

            field_html += '</fieldset>\n'

        elif field_type.__origin__ is Literal:

            # ### Literal ###
            field_html += html_label( field_name )
            #field_html += html_label( field_type.__args__[0], f'{pybiscus_marker} {pybiscus_if_div_active}' )
            field_html += f'<input type="text" value="{field_type.__args__[0]}" {pybiscus_marker} {pybiscus_if_div_active} readonly><br>\n'

        else:

            # ### ??? ###
            field_html += html_label( 'Field Type not handled !!!' )
            field_html += html_label( field_name )

    elif issubclass(field_type, BaseModel):

        field_html += generate_model_html(field_type, inFieldSet )

    else:
        field_html += f' ????<br>\n'

        field_html += f'  <label>{field_name}:   [{type(field_type).__qualname__}]:{(field_type).__qualname__}]</label>\n'
        field_html += f'  <br>\n'

    return field_html



def generate_model_html(model: BaseModel, inFieldSet: bool ) -> str:

    model_html = ''

    if inFieldSet:
        model_html += '<fieldset>\n'
        model_html += f'<legend>{model.__name__}</legend>\n'

    for field_name, field_info in model.model_fields.items():

        model_html += generate_field_html(
                                    field_name        = field_name, 
                                    field_type        = field_info.annotation,
                                    field_required    = field_info.is_required(), 
                                    field_default     = field_info.default, 
                                    field_description = field_info.description,
                                    inFieldSet        = True,
                                    )
   
    if inFieldSet:
        model_html += '</fieldset>\n'
    
    return model_html


print( """

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
        .tab-button.active {
            background-color: #e0e0e0;
        }
        .tab-content {
            padding: 20px;
            border-top: 1px solid #ccc;
        }
        .tab-content:not(.active) {
            display: none;
        }

    </style>


    """)

# Générer le formulaire HTML pour UserModel

if True:
    form_html = generate_model_html(ConfigServer, True)
    print(form_html)
    print('<br><br><br>\n')

if True:
    form_html = generate_model_html(ConfigClient, True)
    print(form_html)
    print('<br><br><br>\n')

if False:
    form_html = generate_model_html(ConfigFabric, True)
    print(form_html)

"""
// Trouver le parent contenant l'attribut data-toto
let parent = enfant.closest("div[data-toto]");

// Vérifier si data-toto est égal à "titi"
if (parent && parent.dataset.toto === "titi") {
    console.log("La valeur de data-toto est 'titi'");
} else {
    console.log("La valeur de data-toto n'est pas 'titi'");
}



element.setAttribute("data-toto", "nouvelleValeur");
console.log(element.getAttribute("data-toto")); 

"""

print("""
<script>
    document.querySelectorAll('.tab-container').forEach(container => {
        container.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', () => {
                // Désactiver tous les onglets dans le même conteneur
                container.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                // Activer l'onglet cliqué et son contenu
                button.classList.add('active');
                container.querySelector(`#${button.dataset.tab}`).classList.add('active');
            });
        });
    });

function traverseDOM(element, callbacks) {
    // Vérifie si l'élément possède l'attribut spécifique
    if (element.hasAttribute('data-custom-attribute')) {
        // Récupère la valeur de l'attribut
        const attributeValue = element.getAttribute('data-custom-attribute');

        // Appelle la fonction de rappel correspondante si elle existe
        if (callbacks[attributeValue]) {
            callbacks[attributeValue](element);
        }
    }

    // Parcourt récursivement les enfants de l'élément
    const children = element.children;
    for (let i = 0; i < children.length; i++) {
        traverseDOM(children[i], callbacks);
    }
}

// Exemple de fonctions de rappel
function handleOption1(element) {
    console.log('Option 1 trouvée:', element);
    // Traitement spécifique pour l'option 1
}

function handleOption2(element) {
    console.log('Option 2 trouvée:', element);
    // Traitement spécifique pour l'option 2
}

function handleOption3(element) {
    console.log('Option 3 trouvée:', element);
    // Traitement spécifique pour l'option 3
}

// Dictionnaire de fonctions de rappel
const callbacks = {
    'option1': handleOption1,
    'option2': handleOption2,
    'option3': handleOption3
};

// Lancer le parcours à partir de l'élément racine, par exemple le body
traverseDOM(document.body, callbacks);

</script>

</body>
</html>
""" )

