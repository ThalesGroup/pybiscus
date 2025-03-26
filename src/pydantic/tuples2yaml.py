
import yaml
from collections import defaultdict

def nested_dict():
    """Helper function to create a nested defaultdict."""
    return defaultdict(nested_dict)

def add_to_dict(d, keys, value, is_list):
    """Add a value to a nested dictionary based on a list of keys."""
    for key in keys[:-1]:
        d = d[key]

    # Check if the value should be added to a list
    if is_list:
        key = keys[-1]
        if key not in d or not isinstance(d[key], list):
            d[key] = []
        d[key].append(value)
    else:
        d[keys[-1]] = value

def parse_tuples_to_yaml(tuples):
    """Convert a list of (key, list_indicator, value) tuples to a nested dictionary."""
    data = nested_dict()

    for key, list_indicator, value in tuples:
        keys = key.split('.')
        is_list = list_indicator == "-"
        add_to_dict(data, keys, value, is_list)

    # Convert defaultdict to a regular dict before serializing to YAML
    return convert_defaultdict_to_dict(data)

def convert_defaultdict_to_dict(d):
    """Recursively convert a defaultdict to a regular dict."""
    if isinstance(d, defaultdict):
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    return d

if __name__ == "__main__":

    # Exemple de paires de tuples
    tuples = [
        ("a.b.c", "-", "v1"),
        ("a.b.c", "-", "v2"),
        ("server.host", "", "localhost"),
        ("server.port", "", "8080"),
        ("database.connection.host", "", "localhost"),
        ("database.connection.port", "", "5432"),
        ("database.connection.options.pool_size", "", "10"),
        ("logging.level", "", "debug"),
    ]

    # Convertir les tuples en structure YAML
    yaml_data = parse_tuples_to_yaml(tuples)

    # Convertir le dictionnaire en chaîne YAML
    yaml_output = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

    print(yaml_output)

