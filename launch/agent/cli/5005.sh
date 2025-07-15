 #!/usr/bin/bash 

# Resolve the directory of the current script (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build the relative config path from the script's directory
CONFIG_PATH="$SCRIPT_DIR/../../../pybiscus_agent_registration_config"

# Launch the Python app with the config path
uv run pybiscus_agent --port 5005 --config "$CONFIG_PATH/agent_5005.yml"
