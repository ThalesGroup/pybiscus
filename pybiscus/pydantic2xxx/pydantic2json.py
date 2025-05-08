from pydantic_core import PydanticUndefined


class PydanticToJson:
    
    @staticmethod
    def generate_description_by_name(type_full_typename, field_name: str, field_default, field_description, prefix):

        import importlib
        import builtins

        if '.' not in type_full_typename:
            # Tenter d'obtenir un type intégré comme 'str', 'int', etc.
            try:
                field_type = getattr(builtins, type_full_typename)
            except AttributeError:
                raise ValueError(f"unknown builtin type : {type_full_typename}")
        else:
            module_name, class_name = full_class_string.rsplit('.', 1)
            try:
                module = importlib.import_module(module_name)
                field_type = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Class '{class_name}' not found in module '{module_name}'") from e
    
        return PydanticToJson.generate_description_by_type(field_type, field_name, field_default, field_description, prefix )

    @staticmethod
    def generate_description_by_type(field_type, field_name: str, field_default, field_description, prefix ) -> dict: # , field_required: bool, field_default, field_description, inFieldSet: bool, prefix: str) -> str:

        if(prefix == ""):
            fq_name = field_name
        else:
            fq_name = f"{prefix}.{field_name}"

        result = { 'name' : field_name, 'fq_name' : fq_name }

        if field_description is not None and field_description is not PydanticUndefined:
            result['description'] = field_description

        if field_default is not None and field_default is not PydanticUndefined:
            result['value'] = field_default

        if field_type is str:

            result['category'] = 'simple'
            result['type'] = 'str'
            result['placeholder'] = 'string'

        elif field_type is int:

            result['category'] = 'simple'
            result['type'] = 'int'
            result['placeholder'] = 'integer'

        elif field_type is float:

            result['category'] = 'simple'
            result['type'] = 'float'
            result['placeholder'] = 'float'

        elif field_type is bool:

            result['category'] = 'simple'
            result['type'] = 'bool'
            result['placeholder'] = 'boolean'
        
        else:

            result['category'] = 'unknown'

        return result
    
if __name__ == "__main__":

    print( PydanticToJson.generate_description_by_name(type_full_typename="str", field_name="a_string", field_default="___", field_description="my test string", prefix="" ) )
    print( PydanticToJson.generate_description_by_name(type_full_typename="int", field_name="an_int", field_default="0", field_description="my test int", prefix="" ) )
