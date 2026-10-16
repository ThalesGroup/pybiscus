import socket
import urllib.parse

import pybiscus.session.manager.session_manager as sm

# The network view of a session: the machines, the processes listening on them (managers, agents,
# Flower servers) and the flows between them, from the one that opens the connection to the one that
# listens. Each manager describes its own part, with a single flow up to its parent; the description
# goes up with the topology, so that the head manager assembles the whole session's.

LOOPBACK_NAMES = ("localhost", "::1", "")


def this_machine() -> str:
    return sm.machine_name or socket.gethostname()


def is_loopback(host: str) -> bool:
    return host in LOOPBACK_NAMES or host.startswith("127.")


def host_and_port(url: str) -> tuple:
    parts = urllib.parse.urlsplit(url or "")
    return parts.hostname or "", parts.port


def machine_of(url: str, declared=None) -> str:
    """the machine an agent declared at its registration, else the host of its address: the loopback
    being this manager's own machine, which alone reaches it there"""
    if declared:
        return declared
    host, _ = host_and_port(url)
    return this_machine() if is_loopback(host) else host


def listened(host) -> str:
    host = (host or "").strip("[]")
    return "all interfaces" if host in ("0.0.0.0", "::") else "loopback" if is_loopback(host) else host


def flower_server_address():
    """the port and the listening address of the session's Flower server, as its session form set them"""
    values = (sm.agent_gui_json_presets or {}).get("values_set") or {}
    listen = values.get("flower_server.listen_address")
    if not listen or ":" not in listen:
        return None, None
    host, _, port = listen.rpartition(":")
    try:
        return int(port), listened(host)
    except ValueError:
        return None, None


def local_view() -> dict:
    """this manager's part: itself, its agents, its session's Flower server, the flows between them,
    its links to its lower levels and its flow up to its parent"""
    from pybiscus.session.manager.upper_level import transport_of

    bouquet = sm.bouquet or "session"
    manager_id = f"{bouquet}/manager"
    processes = [{"id": manager_id, "bouquet": bouquet, "kind": "manager", "name": f"manager {bouquet}",
                  "machine": this_machine(), "port": sm.manager_port, "protocol": "HTTP",
                  "listen": listened(sm.manager_host), "role": "session manager"}]
    flows, problems = [], []

    def flow(source, target, protocol, port, purpose):
        flows.append({"from": source, "to": target, "protocol": protocol, "port": port, "purpose": purpose})

    agent_machine = {}
    for role, registered in (("server", sm.registered_servers), ("client", sm.registered_clients)):
        for name, url in registered.items():
            meta = sm.registered_agents_meta.get(name, {})
            agent_id = f"{bouquet}/agent/{name}"
            relayed = [lower for lower, relay in sm.relays.items() if relay == name]
            agent_machine[name] = machine_of(url, meta.get("machine"))
            processes.append({"id": agent_id, "bouquet": bouquet, "kind": "agent", "name": name,
                              "machine": agent_machine[name], "port": host_and_port(url)[1], "protocol": "HTTP",
                              "listen": None, "role": f"relay of {', '.join(relayed)}" if relayed else f"{role} agent"})
            flow(agent_id, manager_id, "HTTP", sm.manager_port, "registration, states, logs and metrics of its runs")
            flow(manager_id, agent_id, "HTTP", host_and_port(url)[1], "ping, launch and stop of its run")

    port, listen = flower_server_address()
    server = next(iter(sm.registered_servers), None)
    if port and server:
        flower_id = f"{bouquet}/flower"
        processes.append({"id": flower_id, "bouquet": bouquet, "kind": "flower", "name": f"Flower server {bouquet}",
                          "machine": agent_machine[server], "port": port, "protocol": "gRPC", "listen": listen,
                          "role": f"run of {server}"})
        for client in sm.registered_clients:
            relayed = [lower for lower, relay in sm.relays.items() if relay == client]
            flow(f"{bouquet}/agent/{client}", flower_id, "gRPC", port,
                 "relay: the model down, the lower level's aggregate up" if relayed else "training rounds")

    with sm.lower_levels_lock:
        lower_topologies = {lower: report["topology"] for lower, report in sm.lower_levels.items()}
    for lower, relay in sm.relays.items():
        if relay not in sm.registered_clients:
            continue
        lower_server = next((a for a in lower_topologies.get(lower, {}).get("agents", []) if a.get("role") == "server"), None)
        if transport_of(lower) == "manager":
            flow(f"{bouquet}/agent/{relay}", manager_id, "HTTP", sm.manager_port, f"link to {lower}: this manager's mailbox")
        elif lower_server:
            flow(f"{bouquet}/agent/{relay}", f"{lower}/agent/{lower_server['name']}", "files", None,
                 f"link to {lower}: shared directory")
            server_machine = machine_of(lower_server.get("agent_url"), lower_server.get("machine"))
            if server_machine != agent_machine[relay]:
                problems.append(f"the link to {lower} is a shared directory, but its relay ({relay}, on {agent_machine[relay]}) "
                                f"and its server ({lower_server['name']}, on {server_machine}) are on two machines")

    if sm.upper_link is not None:
        upper = sm.upper_link.get("bouquet") or "upper"
        upper_id = f"{upper}/manager"
        host, upper_port = host_and_port(sm.upper_link.get("url"))
        processes.append({"id": upper_id, "bouquet": upper, "kind": "manager", "name": f"manager {upper}",
                          "machine": this_machine() if is_loopback(host) else host, "port": upper_port, "protocol": "HTTP",
                          "listen": None, "role": "upper level's session manager", "external": True})
        link = sm.upper_session_link or {}
        through = link.get("transport") == "manager"
        flow(manager_id, upper_id, "HTTP", upper_port,
             "topology reports; the link of its server, relayed to the mailbox" if through else "topology reports")
        if through and server:
            flow(f"{bouquet}/agent/{server}", manager_id, "HTTP", sm.manager_port, f"link to {upper}: through this manager")
    return {"bouquet": bouquet, "processes": processes, "flows": flows, "problems": problems}


def network_view() -> dict:
    """this manager's part and its lower levels', recursively: the whole session at the head manager"""
    from pybiscus.session.manager.upper_level import lower_levels

    parts = [local_view()]

    def gather(levels):
        for level in levels:
            if level.get("network"):
                parts.append(level["network"])
            gather(level.get("lower_levels", []))

    gather(lower_levels())
    processes, flows, problems = {}, [], []
    for part in parts:
        for process in part["processes"]:
            # a lower level knows its parent only from outside: the parent's own description wins
            if process["id"] not in processes or processes[process["id"]].get("external"):
                processes[process["id"]] = process
        flows += [f for f in part["flows"] if f not in flows]
        problems += part.get("problems", [])
    machines = {}
    for process in processes.values():
        machines.setdefault(process["machine"], []).append(process["id"])
    return {"processes": list(processes.values()), "flows": flows, "problems": problems,
            "machines": [{"name": name, "processes": ids} for name, ids in sorted(machines.items())]}
