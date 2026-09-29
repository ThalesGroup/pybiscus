"""Compare server strategies on short federated runs and print a table of their test metric per round.

Run from the repository root:
    uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_strategies.yml

For every variant of the campaign file, the base server and client configurations are copied with
the variant's strategy, the clients get their share of the training data (train.partition), their
CPU threads (cores / clients) and the campaign's data overrides, then a server and its clients run
on the campaign's port. Configurations, logs and the table go to the output directory.
"""

import argparse
import copy
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from omegaconf import OmegaConf

METRIC_LINE = re.compile(r"📈 gui phase=test round=(\d+) metric=(\S+) value=(\S+)")
ROUND_TIME = re.compile(r"time diff is (\d+(?:\.\d+)?)s")


def deep_merge(base: dict, extra: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        merged[key] = deep_merge(merged[key], value) if isinstance(value, dict) and isinstance(merged.get(key), dict) else value
    return merged


def port_is_free(port: int) -> bool:
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                return False
    return True


def physical_cores() -> int:
    from pybiscus.session.agent.machine import physical_cores as cores
    return cores()


def launch(args: list, log: Path) -> subprocess.Popen:
    # a process group of its own: stopped as a whole, never by a name pattern
    return subprocess.Popen(args, stdout=log.open("w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            os.killpg(process.pid, signal.SIGKILL)


def run_variant(campaign: dict, variant: dict, out: Path) -> dict:
    clients, port = campaign["clients"], campaign["port"]
    label = variant["label"]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    work = out / slug
    work.mkdir(parents=True, exist_ok=True)

    server = OmegaConf.to_container(OmegaConf.load(campaign["server_config"]))
    server["flower_server"]["listen_address"] = f"[::1]:{port}"
    server["server_run"]["num_rounds"] = campaign["rounds"]
    server["server_run"]["reporting"]["basedir"] = str(work / "experiments")
    strategy = copy.deepcopy(variant["strategy"])
    strategy_config = strategy.setdefault("config", {}) or {}
    strategy["config"] = strategy_config
    # every client takes part in every round
    for key in ("min_fit_clients", "min_evaluate_clients", "min_available_clients"):
        strategy_config.setdefault(key, clients)
    server["server_strategy"]["strategy"] = strategy
    server["data"]["config"] = deep_merge(server["data"]["config"], campaign.get("server_data"))
    OmegaConf.save(OmegaConf.create(server), work / "server.yml")

    threads = campaign.get("threads_per_client", "auto")
    if threads == "auto":
        threads = max(1, physical_cores() // clients)
    base_client = OmegaConf.to_container(OmegaConf.load(campaign["client_config"]))
    for i in range(clients):
        client = copy.deepcopy(base_client)
        client["flower_client"]["server_address"] = f"[::1]:{port}"
        client["client_run"]["cid"] = i
        if threads:
            client["client_compute_context"]["num_threads"] = threads
        data = deep_merge(client["data"]["config"], campaign.get("client_data"))
        partition = data.get("train", {}).get("partition")
        if partition is not None:
            partition.update({"num_partitions": clients, "partition_id": i})
        client["data"]["config"] = data
        OmegaConf.save(OmegaConf.create(client), work / f"client_{i}.yml")

    command = [sys.executable, "pybiscus/main.py"]
    started = time.time()
    processes = [launch(command + ["server", "launch", str(work / "server.yml")], work / "server.log")]
    try:
        for _ in range(120):
            if not port_is_free(port) or processes[0].poll() is not None:
                break
            time.sleep(1)
        for i in range(clients):
            processes.append(launch(command + ["client", "launch", str(work / f"client_{i}.yml")], work / f"client_{i}.log"))
        try:
            processes[0].wait(timeout=campaign.get("timeout", 1800))
            status = "ok" if processes[0].returncode == 0 else f"server exit {processes[0].returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
    finally:
        for process in processes:
            stop(process)
    elapsed = time.time() - started

    # the server's own log file: the console output wraps long lines when it is not a terminal
    server_logs = sorted((work / "experiments").glob("*/server_logs.txt"))
    log = server_logs[-1].read_text(errors="replace") if server_logs else ""
    values, metric = {}, None
    for round_number, metric, value in METRIC_LINE.findall(log):
        values[int(round_number)] = float(value)
    round_times = [float(t) for t in ROUND_TIME.findall(log)]
    tracebacks = sum((work / name).read_text(errors="replace").count("Traceback") for name in ["server.log"] + [f"client_{i}.log" for i in range(clients)])
    if tracebacks and status == "ok":
        status = f"{tracebacks} traceback(s)"
    return {"label": label, "metric": metric, "values": values, "round_time": round_times[-1] if round_times else None,
            "elapsed": elapsed, "status": status}


def table(results: list, rounds: int) -> str:
    metric = next((r["metric"] for r in results if r["metric"]), "metric")
    header = "| variant | " + " | ".join(f"round {r}" for r in range(rounds + 1)) + " | s / round | status |"
    lines = [f"test {metric} per round", "", header, "|" + "---|" * (rounds + 4)]
    for r in results:
        cells = [f"{r['values'][n]:.4f}" if n in r["values"] else "—" for n in range(rounds + 1)]
        round_time = f"{r['round_time']:.1f}" if r["round_time"] is not None else "—"
        lines.append(f"| {r['label']} | " + " | ".join(cells) + f" | {round_time} | {r['status']} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign", type=Path, help="campaign file (YAML)")
    parser.add_argument("--only", help="run only the variants whose label starts with this text")
    args = parser.parse_args()

    campaign = OmegaConf.to_container(OmegaConf.load(args.campaign), resolve=True)
    out = Path(campaign.get("output", "experiments/campaigns")) / time.strftime("%Y-%m-%dT%H-%M-%S")
    out.mkdir(parents=True, exist_ok=True)
    if not port_is_free(campaign["port"]):
        sys.exit(f"port {campaign['port']} is in use: choose a free one (the campaign starts its own server)")

    variants = [v for v in campaign["variants"] if not args.only or v["label"].startswith(args.only)]
    results = []
    for number, variant in enumerate(variants, 1):
        print(f"[{number}/{len(variants)}] {variant['label']}", flush=True)
        results.append(run_variant(campaign, variant, out))
        print(table(results[-1:], campaign["rounds"]).splitlines()[-1], flush=True)

    report = table(results, campaign["rounds"])
    (out / "results.md").write_text(report + "\n", encoding="utf-8")
    print("\n" + report + f"\n\nconfigurations, logs and table in {out}")


if __name__ == "__main__":
    main()
