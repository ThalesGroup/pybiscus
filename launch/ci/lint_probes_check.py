"""`pybiscus plugins lint` must still find what the probes of launch/ci/lint-probes/ break: exactly the
rules marked `# expect: <rule>[,<rule>]` on the line each finding names, nothing more. Every rule of
the linter has a probe. Also: a configuration naming a class that is not its category's interface is
refused at `check`, with the class named.

    uv run python launch/ci/lint_probes_check.py
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBES = REPO / "launch/ci/lint-probes"
EXPECT = re.compile(r"#\s*expect:\s*([\w,-]+)")
FINDING = re.compile(r"^(?:❌|⚠️) (?P<file>\S+):(?P<line>\d+): .* \[(?P<rule>[\w-]+)\]$")

sys.path.insert(0, str(REPO))
from pybiscus.commands.apps_common import CONFIG_VALIDATION_EXIT_CODE  # noqa: E402
from pybiscus.plugin.pluginlint import RULES  # noqa: E402


def pybiscus(*args: str, manifests: str) -> subprocess.CompletedProcess:
    # a wide console: rich must not cut a finding's line
    env = {**os.environ, "PYBISCUS_PLUGIN_CONF_PATH": manifests, "COLUMNS": "1000"}
    return subprocess.run([sys.executable, str(REPO / "pybiscus/main.py"), *args], cwd=REPO, env=env,
                          capture_output=True, text=True)


def expected() -> set:
    marks = set()
    for file in sorted(PROBES.rglob("*.py")):
        for number, text in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if match := EXPECT.search(text):
                marks |= {(file.relative_to(REPO).as_posix(), number, rule) for rule in match.group(1).split(",")}
    return marks


def found() -> tuple[set, str]:
    result = pybiscus("plugins", "lint", manifests=str(PROBES / "plugins-conf.yml"))
    output = result.stdout + result.stderr
    findings = {(m["file"], int(m["line"]), m["rule"]) for m in map(FINDING.match, output.splitlines()) if m}
    return findings, output


def check_lint() -> list[str]:
    problems = []
    marks = expected()
    findings, output = found()
    if "plugin(s):" not in output:
        problems.append("the linter did not finish:\n" + output[-2000:])
    problems += [f"not found: {f}:{l} [{r}]" for f, l, r in sorted(marks - findings)]
    problems += [f"unexpected: {f}:{l} [{r}]" for f, l, r in sorted(findings - marks)]
    problems += [f"rule without a probe: {rule}" for rule in sorted(set(RULES) - {r for _, _, r in marks})]
    return problems


def check_refused_interface() -> list[str]:
    manifests = f"pybiscus-plugins/plugins-conf.yml:{PROBES / 'plugins-conf.yml'}"
    base = (PROBES / "client.yml").read_text(encoding="utf-8")
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        for model, code in (("lintprobe_ok", 0), ("lintprobe_interface", CONFIG_VALIDATION_EXIT_CODE)):
            config = Path(tmp) / f"{model}.yml"
            config.write_text(base.replace("name: lintprobe_ok", f"name: {model}"), encoding="utf-8")
            result = pybiscus("client", "check", str(config), manifests=manifests)
            output = result.stdout + result.stderr
            if result.returncode != code:
                problems.append(f"client check with {model}: exit {result.returncode}, {code} expected\n{output[-2000:]}")
            elif code and not ("Skipped plugin classes" in output and "lintprobe_interface" in output):
                problems.append(f"client check with {model}: refused without naming the skipped class\n{output[-2000:]}")
    return problems


def main() -> int:
    lint_problems = check_lint()
    interface_problems = check_refused_interface()
    for problem in lint_problems + interface_problems:
        print(problem)
    print(f"{'FAILED' if lint_problems else 'ok'}       the linter's probes ({len(expected())} expected findings, {len(RULES)} rules)")
    print(f"{'FAILED' if interface_problems else 'ok'}       a class not of its category's interface refused at check")
    return 1 if lint_problems or interface_problems else 0


if __name__ == "__main__":
    sys.exit(main())
