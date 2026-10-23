#!/bin/bash

# Sourced by the managers' scripts: INVITATION = $PYBISCUS_INVITATION, else the only file of
# invitations/received/, else empty. Several files there: the script stops rather than choose.

INVITATION="${PYBISCUS_INVITATION:-}"
if [ -z "$INVITATION" ]; then
	shopt -s nullglob
	received=(invitations/received/*.yml invitations/received/*.yaml)
	shopt -u nullglob
	if [ "${#received[@]}" -gt 1 ]; then
		echo "ERROR: several invitations in invitations/received (${received[*]}): keep one" >&2
		exit 1
	fi
	INVITATION="${received[0]:-}"
fi
