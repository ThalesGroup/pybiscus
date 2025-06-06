import yaml    


def convert_defaultdict_to_dict(d):
    if isinstance(d, dict):
        return {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_defaultdict_to_dict(i) for i in d]
    return d


def set_in_structure(structure, keys, value):
    current = structure
    
    for i, key in enumerate(keys[:-1]):  # all keys except the last
        is_index = key.isdigit()
        key_val = int(key) if is_index else key
        
        if is_index:
            if not isinstance(current, list):
                raise ValueError(f"Expected list but got {type(current)} at key {key}")
            while len(current) <= key_val:
                current.append({})
            current = current[key_val]
        else:
            if key_val not in current:
                # type is determined according to next key
                next_key = keys[i + 1]
                current[key_val] = [] if next_key.isdigit() else {}
            current = current[key_val]
    
    # handle last key
    final_key = keys[-1]
    if final_key.isdigit():
        key_val = int(final_key)
        while len(current) <= key_val:
            current.append(None)
        current[key_val] = value
    else:
        current[final_key] = value


def parse_tuples_to_yaml(tuples):
    data = {}
    for key_path, value in tuples:
        keys = key_path.split(".")
        set_in_structure(data, keys, value)
    return convert_defaultdict_to_dict(data)

def parse_tuples_to_yaml_string(tuples):
    yaml_data = parse_tuples_to_yaml(tuples)
    return yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":

    # test dataset
    tuples = [
        ("d", [] ),
        ("a.b.c.0", "v1"),
        ("a.b.c.1", "v2"),
        ("a.b.c.2", "v2"),
        ("logger.0.name", "rich"),
        ("logger.0.config.empty", True),
        ("logger.1.name", "wandb"),
        ("logger.1.config.key", "abc"),
        ("config.database.host", "localhost"),
        ("config.database.port", 5432),
        ("config.database.ssl", True),
        ("users.0.name", "Alice"),
        ("users.0.age", 30),
        ("users.1.name", "Bob"),
        ("users.1.age", 25),
        ("settings.debug", False),
        ("settings.max_connections", 100),
    ]

    # convert tuples tp YAML
    yaml_data = parse_tuples_to_yaml(tuples)

    # convert to string
    yaml_output = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

    print(yaml_output)

