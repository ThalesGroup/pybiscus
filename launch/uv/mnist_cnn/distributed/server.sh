#!/usr/bin/bash

source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"
export SERVER_PORT="3333"


echo "[uv] server offers service ${SERVICE}"

uv run python pybiscus/main.py server launch ${PYBISCUS_CONF_PATH}/server.yml

