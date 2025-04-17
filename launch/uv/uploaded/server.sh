#!/usr/bin/bash

export SERVER_PORT="3333"


echo "[uv] server offers service ${SERVICE}"

uv run python pybiscus/main.py server launch configs/uploaded/ConfigServer.yml

