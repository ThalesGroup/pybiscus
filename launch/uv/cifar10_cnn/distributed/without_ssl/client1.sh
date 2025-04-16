#!/usr/bin/bash

source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"

echo "[uv] client1 -> server : ${SERVER_ADDRESS}"

uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_1.yml

