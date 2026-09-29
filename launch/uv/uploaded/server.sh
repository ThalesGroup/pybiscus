#!/usr/bin/bash

export SERVER_PORT="3333"


echo "[uv] server offers service ${SERVICE}"

# each agent stores its uploaded configuration under configs/uploaded/<agent port>/
AGENT_PORT="${1:-5000}"

uv run python pybiscus/main.py server launch "configs/uploaded/${AGENT_PORT}/ConfigServer.yml"

