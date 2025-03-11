#!/usr/bin/bash

source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"

echo "[uv] client2 -> server : ${SERVER_ADDRESS}"

uv run python src/main.py client launch ${PYBISCUS_CONF_PATH}/client_2.yml

