"""The federated evaluation of an exported model gives the metrics of the session that trained it:

    evaluation_check.py <trained session's reports> <evaluation session's reports> <evaluation run dir>

The trained session (the smoke run's mnist demo) exported its final model to ONNX; the evaluation session
(configs/onnx_eval, onnxmodel + evaluateonly) evaluated that file on the same data: the server's test and each
site's validation must equal the trained session's last round. A file whose hash differs stops the server.
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# both runs on the CPU (smoke_configs.py): torch and onnxruntime differ by the order of their float sums
TOLERANCE = 1e-4

trained, evaluated, run_dir = (Path(p).resolve() for p in sys.argv[1:4])
failed = []


def judge(ok: bool, message: str, detail: str = "") -> None:
    print(f"  {'ok      ' if ok else 'FAILED  '} {message}{'' if ok or not detail else f' ({detail})'}", flush=True)
    if not ok:
        failed.append(message)


def last_round_metrics(metrics_file: Path) -> dict:
    """{'glob' or cid: {metric: value}} of the evaluation (val_*) at the last step of metrics.txt"""
    steps = {}
    for line in metrics_file.read_text().splitlines():
        found = re.search(r"\[step (\d+)\] (\{.*\})$", line)
        if found:
            steps.setdefault(int(found[1]), {}).update(ast.literal_eval(found[2]))
    last = steps[max(steps)]
    values = {}
    for key, value in last.items():
        parts = re.fullmatch(r"val_(.+)_([^_]+)", key)
        if parts and parts[1] != "cid":
            values.setdefault(parts[2], {})[parts[1]] = value
    return values


def close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= TOLERANCE


expected = last_round_metrics(trained / "metrics.txt")
report = json.loads((evaluated / "evaluation.json").read_text())
last = report["rounds"][-1]
model = run_dir / "experiments/published/mnist_cnn.onnx"

import hashlib
judge(report["model"]["name"] == "onnxmodel" and report["model"]["config"]["sha256"] == hashlib.sha256(model.read_bytes()).hexdigest(),
      "the report names the model evaluated and its SHA-256", json.dumps(report["model"]))
judge(not any(key.startswith("fit_") for key in (evaluated / "metrics.txt").read_text().split("'")),
      "no client trained in the evaluation session")

server = last["server"] or {}
for metric in ("loss", "accuracy"):
    judge(close(server.get("metrics", {}).get(metric), expected.get("glob", {}).get(metric)),
          f"the server's test, {metric}: ONNX equals the trained session",
          f"{server.get('metrics', {}).get(metric)} vs {expected.get('glob', {}).get(metric)}")
sites = {site["cid"]: site for site in last["sites"]}
judge(set(sites) == set(expected) - {"glob"}, "the report has every site", f"{sorted(sites)} vs {sorted(set(expected) - {'glob'})}")
for cid, site in sorted(sites.items()):
    for metric in ("loss", "accuracy"):
        judge(close(site["metrics"].get(metric), expected.get(cid, {}).get(metric)),
              f"site {cid}, {metric}: ONNX equals the trained session",
              f"{site['metrics'].get(metric)} vs {expected.get(cid, {}).get(metric)}")
mean = last["weighted_mean"]
judge(mean is not None and abs(mean["loss"] - sum(s["loss"] * s["num_examples"] for s in sites.values()) / mean["num_examples"]) < 1e-9,
      "the weighted mean of the sites")

env = {**os.environ, "PYBISCUS_ONNX_MODEL": str(model), "PYBISCUS_ONNX_SHA256": "f" * 64}
refused = subprocess.run(sys.argv[4:] + ["server", "launch", "configs/server.yml", "--server-listen-address", "[::]:0"],
                         cwd=run_dir, env=env, capture_output=True, text=True, timeout=600)
output = " ".join((refused.stdout + refused.stderr).split())
judge(refused.returncode != 0 and "the session expects" in output, "a file whose SHA-256 differs stops the server",
      f"exit {refused.returncode}")

sys.exit(1 if failed else 0)
