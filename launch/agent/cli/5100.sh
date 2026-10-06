#!/usr/bin/bash 

# Resolve the directory of the current script (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build the relative config path from the script's directory
CONFIG_PATH="$SCRIPT_DIR/../../../pybiscus_agent_registration_config"

# the server of a lower-level session: the hierarchical plugins too (an exported PYBISCUS_PLUGIN_CONF_PATH prevails)
REPO_ROOT="$SCRIPT_DIR/../../.."
export PYBISCUS_PLUGIN_CONF_PATH="${PYBISCUS_PLUGIN_CONF_PATH:-$REPO_ROOT/pybiscus-plugins/plugins-conf.yml:$REPO_ROOT/pybiscus-plugins-hierarchical/plugins-conf.yml}"

# Launch the Python app with the config path
uv run pybiscus_agent --port 5100 --config "$CONFIG_PATH/agent_5100.yml" "$@"
