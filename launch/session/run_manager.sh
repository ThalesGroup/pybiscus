#!/bin/bash

uv run session_manager \
	--port 5555 --bouquet cortaixlabs-core --location palaiseau-dc --geo 48.71439,2.20278 "$@"

