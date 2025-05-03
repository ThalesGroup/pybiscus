#!/usr/bin/bash

NB="02"

uv run python pybiscus/session/register/register_client.py \
	--name cortaix-labs-${NB} \
	--client-url http://localhost:50${NB} \
	--manager-url http://localhost:5555

