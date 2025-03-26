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


