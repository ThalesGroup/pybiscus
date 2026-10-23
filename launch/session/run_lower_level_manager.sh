#!/bin/bash

# Second manager, for a lower-level session of a hierarchical FL session, next to the upper-level
# one of run_manager.sh (port 5555). Its own port gives it its own tokens
# (.pybiscus-cache/tokens/manager-<port>-*) and its own vignettes; the lower-level agents register
# with it (pybiscus_agent_registration_config/agent_510{0..8}.yml). Another port for a further
# lower-level session: PYBISCUS_LOWER_MANAGER_PORT=5557 and its own --bouquet.
# It reports its bouquet's topology to the upper-level manager (PYBISCUS_UPPER_MANAGER_URL, default
# http://localhost:5555), whose page then shows the bouquets' tree and the lower-level agents.
# Its agents in one page, for a test on one machine:
#   3frames.html?server=5100&client=5101&clients=8&bouquet=cortaixlabs-edge1
# With an invitation of the upper level (invitations/received/, or $PYBISCUS_INVITATION), it starts
# with it: the invitation gives its bouquet, the upper level's URL and its token.

source "$(dirname "$0")/received_invitation.sh"
if [ -n "$INVITATION" ]; then
	identity=(--invitation "$INVITATION")
else
	identity=(--bouquet cortaixlabs-edge1 --upper-url "${PYBISCUS_UPPER_MANAGER_URL:-http://localhost:5555}")
fi

PYBISCUS_INVITATION= uv run session_manager \
	--port "${PYBISCUS_LOWER_MANAGER_PORT:-5556}" \
	"${identity[@]}" \
	--location palaiseau-dc \
	--geo 48.71439,2.20278 \
	"$@"
