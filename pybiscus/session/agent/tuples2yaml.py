import yaml

def convert_defaultdict_to_dict(d):
    if isinstance(d, dict):
        return {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_defaultdict_to_dict(i) for i in d]
    return d

def set_in_structure(structure, keys, value):
    current = structure
    for i, key in enumerate(keys):
        is_last = i == len(keys) - 1
        is_index = key.isdigit()
        key_val = int(key) if is_index else key

        # Convert to list if needed
        if is_index:
            if not isinstance(current, list):
                current_parent[last_key] = []
                current = current_parent[last_key]
            while len(current) <= key_val:
                current.append({})
            if is_last:
                current[key_val] = value
            else:
                current = current[key_val]
        else:
            if is_last:
                current[key_val] = value
            else:
                if key_val not in current or not isinstance(current[key_val], (dict, list)):
                    current[key_val] = {}
                current_parent = current
                current = current[key_val]

        last_key = key_val

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
    ]

    # convert tuples tp YAML
    yaml_data = parse_tuples_to_yaml(tuples)

    # convert to string
    yaml_output = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

    print(yaml_output)

