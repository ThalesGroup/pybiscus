import os
import socket


def machine_name() -> str:
    return socket.gethostname()


def physical_cores() -> int:
    """physical cores this agent may use: the manager shares them between the clients of a machine"""

    logical = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    # psutil is not a dependency: /proc/cpuinfo lists a (physical id, core id) pair per core
    cores, current = set(), {}
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                key, _, value = line.partition(":")
                key = key.strip()
                if key in ("physical id", "core id"):
                    current[key] = value.strip()
                elif not line.strip() and current:
                    cores.add((current.get("physical id"), current.get("core id")))
                    current = {}
        if current:
            cores.add((current.get("physical id"), current.get("core id")))
    except OSError:
        pass
    # a container may be given fewer CPUs than the host's cores
    return max(1, min(len(cores), logical) if cores else logical)
