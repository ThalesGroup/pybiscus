#!/bin/bash

uv run python pybiscus/session/manager/start_manager.py \
	--port 5555 \
	--server-url http://localhost:5000

