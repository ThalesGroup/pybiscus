"""The federated evaluation on the sites' test section, at scheduled rounds:

    evaluation_section_check.py --prepare <configs dir>
    evaluation_section_check.py <run dir>

--prepare turns configs/onnx_eval (the smoke's) into an evaluation of each site's test section, its
max_samples the server's, at rounds every 5 s. The check then requires, for each round, each site's
metrics equal to the server's test (the same examples, the same model), the report naming the section,
the schedule's deadlines in the server's log, and no fit.
"""

import json
import re
import sys
from pathlib import Path

import yaml

TOLERANCE = 1e-6

if sys.argv[1] == "--prepare":
    configs = Path(sys.argv[2])
    server = yaml.safe_load((configs / "server.yml").read_text())
    for step in server["server_strategy"]["pipeline"]:
        if step["name"] == "evaluateonly":
            step["config"]["section"] = "test"
    server["server_run"]["schedule"] = {"every": "5s"}
    (configs / "server.yml").write_text(yaml.safe_dump(server, sort_keys=False))
    for name in ("client_1", "client_2"):
        client = yaml.safe_load((configs / f"{name}.yml").read_text())
        client["data"]["config"]["test"] = dict(server["data"]["config"]["test"])
        (configs / f"{name}.yml").write_text(yaml.safe_dump(client, sort_keys=False))
    sys.exit(0)

run_dir = Path(sys.argv[1])
failed = []


def judge(ok: bool, message: str, detail: str = "") -> None:
    print(f"  {'ok      ' if ok else 'FAILED  '} {message}{'' if ok or not detail else f' ({detail})'}", flush=True)
    if not ok:
        failed.append(message)


report = json.loads(next(run_dir.glob("experiments/**/evaluation.json")).read_text())
judge(report.get("section") == "test", "the report names the section evaluated, test", str(report.get("section")))
rounds = report["rounds"]
for entry in rounds:
    server = (entry["server"] or {}).get("metrics", {})
    for site in entry["sites"]:
        gaps = {m: abs(site["metrics"].get(m, float("inf")) - server.get(m, float("-inf"))) for m in ("loss", "accuracy", "f1_macro")}
        judge(all(gap <= TOLERANCE for gap in gaps.values()) and site["num_examples"] == 2000,
              f"round {entry['round']}, site {site['cid']}: its test section gives the server's test",
              f"{gaps}, {site['num_examples']} examples")
judge([len(entry["sites"]) for entry in rounds] == [2, 2], "two scheduled rounds, both sites in each",
      str([(entry["round"], len(entry["sites"])) for entry in rounds]))
log = " ".join((run_dir / "server.log").read_text(errors="replace").split())
judge("next round at" in log and "rounds=2/2" in log, "the rounds follow the schedule and both count")
judge(not any("Training Finished" in (run_dir / f"{name}.log").read_text(errors="replace") for name in ("client_1", "client_2")),
      "no client trained")
sys.exit(1 if failed else 0)
