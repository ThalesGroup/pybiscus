"""Derive the smoke run's configurations from a shipped demo: smoke_configs.py <demo dir> <output dir> <max samples> <threads>

The demo's own files are used, not copies kept aside: a demo left behind by a change of the
configuration models fails here.
"""

import sys
from pathlib import Path

from omegaconf import OmegaConf

demo, output, max_samples, threads = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])

for name in ("server", "client_1", "client_2"):
    conf = OmegaConf.load(demo / f"{name}.yml")
    context = conf["server_compute_context" if name == "server" else "client_compute_context"]
    # a runner has no GPU, and the same hardware everywhere keeps the run comparable
    context.hardware.accelerator = "cpu"
    # without it every process takes all the cores, and three of them on one machine crawl
    context.num_threads = threads
    for section in ("train", "test"):
        if section in conf.data.config:
            conf.data.config[section].max_samples = max_samples
    OmegaConf.save(conf, output / f"{name}.yml")
