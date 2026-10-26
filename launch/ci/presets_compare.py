"""The second half of presets_check.py, in the repository's environment (it loads the plugins): the
presets applied in Python to the form's base, compared with the form's configuration once validated."""

import io
import json
import sys
from contextlib import redirect_stdout

with redirect_stdout(io.StringIO()):
    # the plugin manager says what it loads
    from pybiscus.flower_config.config_client import ConfigClient
    from pybiscus.flower_config.config_server import ConfigServer
from pybiscus.session.agent import presets

MODELS = {"server": ConfigServer, "client": ConfigClient}


def as_texts(value):
    if isinstance(value, dict):
        return {k: as_texts(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_texts(v) for v in value]
    return None if value is None else presets.as_text(value)


def validated(model, config) -> tuple[str, object]:
    # both are text as the form reads it: compared once validated, "2" and 2 are the same
    try:
        return "valid", model.model_validate(config).model_dump(mode="json")
    except ValueError:
        return "invalid", as_texts(config)


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            yield from differences(a.get(key, "<absent>"), b.get(key, "<absent>"), f"{path}.{key}")
    elif a != b:
        yield f"{path[1:]}: form {a!r}, python {b!r}"


def main() -> int:
    dump = json.load(open(sys.argv[1]))
    failures = 0
    for name, case in dump["cases"].items():
        model = MODELS[case["role"]]
        config, unplaced, ignored = presets.apply(model, dump["bases"][case["role"]], case["presets"])
        (form_state, form), (python_state, python) = validated(model, case["form"]), validated(model, config)
        found = list(differences(form, python))
        same = form_state == python_state and not found
        failures += not same
        print(f"  {'ok    ' if same else 'FAILED'}   {name} ({case['role']}, form {form_state}, python {python_state})"
              + (f"; no place for {', '.join(unplaced)}" if unplaced else "")
              + (f"; ignored {', '.join(ignored)}" if ignored else ""))
        for line in found[:20]:
            print(f"             {line}")
    print(f"  {len(dump['cases'])} case(s), {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
