#!/usr/bin/bash

source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"

echo "[uv] server offers service ${SERVICE}"

uv run python src/main.py server launch ${PYBISCUS_CONF_PATH}/server.yml

