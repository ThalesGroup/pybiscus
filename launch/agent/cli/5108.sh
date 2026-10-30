#!/usr/bin/bash 

# Resolve the directory of the current script (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build the relative config path from the script's directory
CONFIG_PATH="$SCRIPT_DIR/../../../pybiscus_agent_registration_config"

# an invitation of the manager (invitations/received/, or $PYBISCUS_AGENT_INVITATION) gives the
# agent's name, role and token, over the configuration's
CONFIG_FILE="$CONFIG_PATH/agent_5108.yml"
source "$SCRIPT_DIR/../received_agent_invitation.sh"
invitation=()
[ -n "$AGENT_INVITATION" ] && invitation=(--invitation "$AGENT_INVITATION")

# Launch the Python app with the config path
# 3frames.html, served by launch/agent/3frames.sh, shows this agent in a frame
PYBISCUS_AGENT_INVITATION= uv run pybiscus_agent --port 5108 --config "$CONFIG_FILE" --frame-ancestor "http://localhost:${PYBISCUS_3FRAMES_PORT:-5550}" "${invitation[@]}" "$@"
