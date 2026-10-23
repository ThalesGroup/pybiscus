#!/bin/bash

# With an invitation of an upper level (invitations/received/, or $PYBISCUS_INVITATION), this
# manager is itself a lower level: the invitation gives its bouquet, the upper level's URL and token.
# --require-invitation (or PYBISCUS_REQUIRE_INVITATION=1) refuses its own lower levels without one.

source "$(dirname "$0")/received_invitation.sh"
if [ -n "$INVITATION" ]; then
	identity=(--invitation "$INVITATION")
else
	identity=(--bouquet cortaixlabs-core)
fi

PYBISCUS_INVITATION= uv run session_manager \
	--port 5555 \
	"${identity[@]}" \
	--location palaiseau-dc \
	--geo 48.71439,2.20278 \
	"$@"

