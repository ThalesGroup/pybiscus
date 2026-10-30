#!/usr/bin/bash

# 3frames.html on http://localhost:5550, the origin the agents of launch/agent/cli allow to frame
# them; another port: PYBISCUS_3FRAMES_PORT, given to the agents' scripts too. The page's parameters
# as the first argument: launch/agent/3frames.sh "server=5100&client=5101&clients=8"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run python "$SCRIPT_DIR/serve_3frames.py" --port "${PYBISCUS_3FRAMES_PORT:-5550}" --query "${1:-}"
