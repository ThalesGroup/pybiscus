import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import ClassVar, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm

# The link between two levels of a hierarchical session, shared by the upper level's relay client
# (plugin "client") and the lower level's server decorator (plugin "strategydecorator"): two plugins
# must not import each other. Round r: the relay publishes the upper model, the lower server takes
# it, trains a round on it and publishes its aggregate, which the relay sends up as its fit result.


class ConfigSessionLink(BaseModel):

    # the config section of both plugins: pydantic2html names a nested model's fields after it
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    directory: str = Field(default="/tmp/pybiscus-links", description=
        "directory shared by the relay and the lower level's server, on the machine where both run")
    link_id: str = Field(default="link", description=
        "the same on both ends; a new one for each hierarchical run, files of an earlier run being taken otherwise")
    timeout: float = Field(default=3600, gt=0, description=
        "seconds to wait for the other level: a whole round of the lower level, or between two rounds of the upper level")
    poll_interval: float = Field(default=0.5, gt=0, description="seconds between two looks at the directory")

    model_config = ConfigDict(extra="forbid")


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


def scalar_metrics(metrics: Optional[dict]) -> dict:
    """what a json file and a Flower result both carry"""
    return {key: value for key, value in (metrics or {}).items()
            if isinstance(value, (bool, int, float, str)) and not (isinstance(value, float) and np.isnan(value))}
