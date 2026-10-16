import io
import json
import os
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import ClassVar, Literal, Optional, get_args

import numpy as np
import requests
from pydantic import BaseModel, ConfigDict, Field, model_validator

import pybiscus.core.pybiscus_logger as logm

# The link between two levels of a hierarchical session, shared by the upper level's relay client
# (plugin "client") and the lower level's server decorator (plugin "strategydecorator"): two plugins
# must not import each other. Round r: the relay publishes the upper model, the lower server takes
# it, trains a round on it and publishes its aggregate, which the relay sends up as its fit result.
# Two transports: a directory both ends share (one machine), or the mailbox of the upper level's
# session manager, which each end reaches through its own manager (any machines).


class ConfigSessionLink(BaseModel):

    # the config section of both plugins: pydantic2html names a nested model's fields after it
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    transport: Literal["directory", "manager"] = Field(default="directory", description=
        "directory: files in a directory shared by the relay and the lower level's server, on one machine; "
        "manager: the mailbox of the upper level's session manager, over HTTP, the two ends on any machines")
    directory: str = Field(default="/tmp/pybiscus-links", description=
        "transport directory: directory shared by the relay and the lower level's server, on the machine where both run")
    # a plain string rather than Optional: the managers set and lock it in the forms like the other fields
    manager_url: str = Field(default="", description=
        "transport manager: this end's own session manager (the relay's: the upper level's; the lower server's: its "
        "level's, which relays to the upper one)")
    link_id: str = Field(default="link", description=
        "the same on both ends; a new one for each hierarchical run, files of an earlier run being taken otherwise")
    timeout: float = Field(default=3600, gt=0, description=
        "seconds to wait for the other level: a whole round of the lower level, or between two rounds of the upper level")
    poll_interval: float = Field(default=0.5, gt=0, description="transport directory: seconds between two looks at the directory")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def manager_transport_needs_its_manager(self):
        if self.transport == "manager" and not self.manager_url:
            raise ValueError("transport manager needs manager_url: this end's own session manager")
        return self


class SessionLinkError(Exception):
    pass


class DirectoryLink:
    """files <directory>/<link_id>/{model,aggregate}_<round>.{npz,json}: the json, written last,
    says the arrays are complete"""

    def __init__(self, config: ConfigSessionLink):
        self.config = config
        self.path = Path(config.directory) / config.link_id

    def reset(self) -> None:
        """called by the relay before its first round: the upper level starts each exchange"""
        shutil.rmtree(self.path, ignore_errors=True)
        self.path.mkdir(parents=True, exist_ok=True)

    def publish_model(self, server_round: int, arrays: list) -> None:
        self._publish("model", server_round, arrays, {})

    def wait_model(self, server_round: int) -> list:
        arrays, _ = self._wait("model", server_round)
        return arrays

    def publish_aggregate(self, server_round: int, arrays: list, num_examples: int, metrics: dict) -> None:
        self._publish("aggregate", server_round, arrays, {"num_examples": num_examples, "metrics": metrics})

    def publish_failure(self, server_round: int, reason: str) -> None:
        self._publish("aggregate", server_round, [], {"failure": reason})

    def wait_aggregate(self, server_round: int) -> tuple:
        arrays, header = self._wait("aggregate", server_round)
        if "failure" in header:
            raise SessionLinkError(f"the lower level failed its round {server_round}: {header['failure']}")
        return arrays, header["num_examples"], header["metrics"]

    def _files(self, kind: str, server_round: int) -> tuple:
        stem = self.path / f"{kind}_{server_round:04d}"
        return stem.with_suffix(".npz"), stem.with_suffix(".json")

    def _publish(self, kind: str, server_round: int, arrays: list, header: dict) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        arrays_file, header_file = self._files(kind, server_round)
        # written aside then renamed: the other level never reads a half-written file
        with tempfile.NamedTemporaryFile(dir=self.path, suffix=".npz", delete=False) as tmp:
            np.savez(tmp, *arrays)
        os.replace(tmp.name, arrays_file)
        with tempfile.NamedTemporaryFile("w", dir=self.path, suffix=".json", delete=False) as tmp:
            json.dump({**header, "arrays": len(arrays)}, tmp)
        os.replace(tmp.name, header_file)
        logm.console.log(f"🔗 link {self.config.link_id}: {kind} of round {server_round} published")

    def _wait(self, kind: str, server_round: int) -> tuple:
        arrays_file, header_file = self._files(kind, server_round)
        deadline = time.monotonic() + self.config.timeout
        logm.console.log(f"🔗 link {self.config.link_id}: waiting for the {kind} of round {server_round}")
        while not header_file.exists():
            if time.monotonic() > deadline:
                raise SessionLinkError(f"no {kind} of round {server_round} in {self.path} after {self.config.timeout} s")
            time.sleep(self.config.poll_interval)
        header = json.loads(header_file.read_text())
        # no pickle: a shared directory must not run the code of whoever writes in it
        with np.load(arrays_file, allow_pickle=False) as npz:
            arrays = [npz[f"arr_{index}"] for index in range(header["arrays"])]
        # read once: a file left behind would be taken again by the next run of a reused link_id
        arrays_file.unlink(missing_ok=True)
        header_file.unlink(missing_ok=True)
        return arrays, header


# the transports a link may use, as its configuration declares them
LINK_TRANSPORTS = get_args(ConfigSessionLink.model_fields["transport"].annotation)

# the json header of a published object (arrays, num_examples, metrics, failure), beside its arrays
LINK_HEADER = "X-Pybiscus-Link"
# a manager holds a wait at most this long: the link asks again until its timeout
MAX_WAIT_S = 30


class ManagerLink(DirectoryLink):
    """the same exchanges through a session manager's mailbox: PUT, GET (which waits for the object)
    and DELETE on /pybiscus-session/link/<link_id>/...; the object is taken out once read"""

    def __init__(self, config: ConfigSessionLink):
        self.config = config
        self.base = f"{config.manager_url.rstrip('/')}/pybiscus-session/link/{urllib.parse.quote(config.link_id, safe='')}"

    def _headers(self) -> dict:
        # the token of this end's session: the relay's manager is its session's, the lower server's too
        from pybiscus.session.auth import headers_for
        return headers_for(self.config.manager_url)

    def reset(self) -> None:
        response = requests.delete(self.base, headers=self._headers(), timeout=10)
        if not response.ok:
            raise SessionLinkError(f"the session manager refused to reset the link {self.config.link_id}: HTTP {response.status_code} {response.text.strip()}")

    def _publish(self, kind: str, server_round: int, arrays: list, header: dict) -> None:
        buffer = io.BytesIO()
        np.savez(buffer, *arrays)
        headers = {**self._headers(), LINK_HEADER: json.dumps({**header, "arrays": len(arrays)}),
                   "Content-Type": "application/octet-stream"}
        deadline = time.monotonic() + self.config.timeout
        while True:
            try:
                response = requests.put(f"{self.base}/{kind}/{server_round}", data=buffer.getvalue(), headers=headers, timeout=60)
                if response.ok:
                    break
                raise SessionLinkError(f"the session manager refused the {kind} of round {server_round}: HTTP {response.status_code} {response.text.strip()}")
            except requests.ConnectionError:
                # the manager out of reach for a moment: it may come back
                if time.monotonic() > deadline:
                    raise SessionLinkError(f"no session manager at {self.config.manager_url} for {self.config.timeout} s")
                time.sleep(self.config.poll_interval)
        logm.console.log(f"🔗 link {self.config.link_id}: {kind} of round {server_round} published ({len(buffer.getvalue()) // 1024} kB)")

    def _wait(self, kind: str, server_round: int) -> tuple:
        deadline = time.monotonic() + self.config.timeout
        logm.console.log(f"🔗 link {self.config.link_id}: waiting for the {kind} of round {server_round}")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SessionLinkError(f"no {kind} of round {server_round} at {self.config.manager_url} after {self.config.timeout} s")
            wait = min(MAX_WAIT_S, remaining)
            try:
                response = requests.get(f"{self.base}/{kind}/{server_round}", params={"wait": wait},
                                        headers=self._headers(), timeout=wait + 30)
            except requests.ConnectionError:
                time.sleep(self.config.poll_interval)
                continue
            if response.status_code == 204:
                continue
            if not response.ok:
                raise SessionLinkError(f"the session manager refused the {kind} of round {server_round}: HTTP {response.status_code} {response.text.strip()}")
            header = json.loads(response.headers[LINK_HEADER])
            # no pickle: arrays only, whoever wrote them
            with np.load(io.BytesIO(response.content), allow_pickle=False) as npz:
                arrays = [npz[f"arr_{index}"] for index in range(header["arrays"])]
            return arrays, header


def make_link(config: ConfigSessionLink):
    return ManagerLink(config) if config.transport == "manager" else DirectoryLink(config)


def scalar_metrics(metrics: Optional[dict]) -> dict:
    """what a json file and a Flower result both carry"""
    return {key: value for key, value in (metrics or {}).items()
            if isinstance(value, (bool, int, float, str)) and not (isinstance(value, float) and np.isnan(value))}
