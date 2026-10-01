"""Compare server strategies on short federated runs and print a table of their test metric per round.

Run from the repository root:
    uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_strategies.yml

For every variant of the campaign file, the base server and client configurations are copied with
the variant's strategy, the clients get their share of the training data (train.partition), their
CPU threads (cores / clients) and the campaign's data overrides, then a server and its clients run
on the campaign's port. Configurations, logs and the table go to the output directory.

With seeds: [s1, s2, ...], every variant runs once per seed (server_run.seed, each client's
client_run.seed, the byzantine clients' seed, and with seed_partitions: true the data partition)
and a second table gives the mean ± standard deviation of the seeds.
"""

import argparse
import copy
import os
import re
import signal
import socket
import statistics
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


def with_work(obj, work: Path):
    """"{work}" in the strings of obj replaced by the variant's directory: a directory of its own
    (the colluders' shared one, for instance) without files left by an earlier run"""
    if isinstance(obj, dict):
        return {k: with_work(v, work) for k, v in obj.items()}
    if isinstance(obj, list):
        return [with_work(v, work) for v in obj]
    return obj.replace("{work}", str(work)) if isinstance(obj, str) else obj


def port_is_free(port: int) -> bool:
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                return False
    return True


def physical_cores() -> int:
    from pybiscus.session.agent.machine import physical_cores as cores
    return cores()


def launch(args: list, log: Path, env: dict = None) -> subprocess.Popen:
    # a process group of its own: stopped as a whole, never by a name pattern
    return subprocess.Popen(args, stdout=log.open("w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            start_new_session=True, env=env)


def plugin_env(campaign: dict) -> dict:
    """the campaign's extra plugin manifests (test-only plugins such as byzantine) appended to the
    default one"""
    env = dict(os.environ)
    extra = campaign.get("plugin_manifests") or []
    if extra:
        base = env.get("PYBISCUS_PLUGIN_CONF_PATH", "pybiscus-plugins-conf.yml")
        env["PYBISCUS_PLUGIN_CONF_PATH"] = ":".join([base, *extra])
    return env


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            os.killpg(process.pid, signal.SIGKILL)


def run_variant(campaign: dict, variant: dict, out: Path, seed: int = None) -> dict:
    clients, port = campaign["clients"], campaign["port"]
    label = variant["label"] if seed is None else f"{variant['label']} (seed {seed})"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    work = out / slug
    work.mkdir(parents=True, exist_ok=True)

    server = OmegaConf.to_container(OmegaConf.load(campaign["server_config"]))
    server["flower_server"]["listen_address"] = f"[::1]:{port}"
    server["server_run"]["num_rounds"] = campaign["rounds"]
    if "local_epochs" in campaign:
        server["server_run"]["clients_fit_local_epochs"] = campaign["local_epochs"]
    server["server_run"]["reporting"]["basedir"] = str(work / "experiments")
    if seed is not None:
        server["server_run"]["seed"] = seed
    strategy = copy.deepcopy(variant["strategy"])
    strategy_config = strategy.setdefault("config", {}) or {}
    strategy["config"] = strategy_config
    # every client takes part in every round
    for key in ("min_fit_clients", "min_evaluate_clients", "min_available_clients"):
        strategy_config.setdefault(key, clients)
    server["server_strategy"]["strategy"] = strategy
    # first in the pipeline: closest to the strategy, so that the base decorators (saved
    # parameters, timings) see what the variant's decorators produce
    server["server_strategy"]["pipeline"] = copy.deepcopy(variant.get("pipeline", [])) + server["server_strategy"]["pipeline"]
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
            if seed is not None and campaign.get("seed_partitions"):
                partition["seed"] = seed
        client["data"]["config"] = data
        # merged last: a variant may change one client only (a malicious one, for instance)
        overrides = {int(k): with_work(v, work.resolve()) for k, v in (variant.get("client_overrides") or {}).items()}
        client = deep_merge(client, overrides.get(i))
        if seed is not None:
            # one seed per client: the same one would give every client the same batch order
            client["client_run"]["seed"] = seed * 1000 + i
            alternate = client["flower_client"].get("alternate_client_class") or {}
            if alternate.get("name") == "byzantine":
                alternate.setdefault("config", {}).setdefault("seed", seed)
        OmegaConf.save(OmegaConf.create(client), work / f"client_{i}.yml")

    command = [sys.executable, "pybiscus/main.py"]
    env = plugin_env(campaign)
    started = time.time()
    processes = [launch(command + ["server", "launch", str(work / "server.yml")], work / "server.log", env)]
    try:
        for _ in range(120):
            if not port_is_free(port) or processes[0].poll() is not None:
                break
            time.sleep(1)
        for i in range(clients):
            processes.append(launch(command + ["client", "launch", str(work / f"client_{i}.yml")], work / f"client_{i}.log", env))
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
    return {"label": label, "variant": variant["label"], "seed": seed, "metric": metric, "values": values, "round_time": round_times[-1] if round_times else None,
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


def summary(results: list, rounds: int) -> str:
    """mean ± sample standard deviation of each variant's seeds, round by round"""
    metric = next((r["metric"] for r in results if r["metric"]), "metric")
    by_variant = {}
    for r in results:
        by_variant.setdefault(r["variant"], []).append(r)
    header = "| variant | " + " | ".join(f"round {r}" for r in range(rounds + 1)) + " | seeds | status |"
    lines = [f"test {metric} per round, mean ± std over the seeds", "", header, "|" + "---|" * (rounds + 4)]
    for variant, runs in by_variant.items():
        cells = []
        for n in range(rounds + 1):
            values = [r["values"][n] for r in runs if n in r["values"]]
            if not values:
                cells.append("—")
            elif len(values) == 1:
                cells.append(f"{values[0]:.4f}")
            else:
                cells.append(f"{statistics.mean(values):.4f} ± {statistics.stdev(values):.4f}")
        failed = [f"seed {r['seed']}: {r['status']}" for r in runs if r["status"] != "ok"]
        lines.append(f"| {variant} | " + " | ".join(cells) + f" | {len(runs)} | {'; '.join(failed) or 'ok'} |")
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
    seeds = campaign.get("seeds") or [None]
    runs = [(variant, seed) for variant in variants for seed in seeds]
    results = []
    for number, (variant, seed) in enumerate(runs, 1):
        print(f"[{number}/{len(runs)}] {variant['label']}" + ("" if seed is None else f" (seed {seed})"), flush=True)
        results.append(run_variant(campaign, variant, out, seed))
        print(table(results[-1:], campaign["rounds"]).splitlines()[-1], flush=True)

    report = table(results, campaign["rounds"])
    if seeds != [None]:
        report += "\n\n" + summary(results, campaign["rounds"])
    (out / "results.md").write_text(report + "\n", encoding="utf-8")
    print("\n" + report + f"\n\nconfigurations, logs and table in {out}")


if __name__ == "__main__":
    main()
