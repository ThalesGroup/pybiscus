#!/bin/bash

# Sourced by launch/agent/cli/<port>.sh, CONFIG_FILE set: AGENT_INVITATION = $PYBISCUS_AGENT_INVITATION,
# else invitations/received/<bouquet>_agent_<agent_name>.yml, the names read in the configuration,
# else the only agent invitation there (its name prevails over the configuration's), else empty.
# Several and none named after this agent: the script stops rather than choose.

AGENT_INVITATION="${PYBISCUS_AGENT_INVITATION:-}"
if [ -z "$AGENT_INVITATION" ] && [ -d invitations/received ]; then
	# the plain "key: value" lines of the registration configurations, quoted or not
	config_value() {
		sed -n "s/^$1:[[:space:]]*[\"']\{0,1\}\([^\"'#]*\)[\"']\{0,1\}.*/\1/p" "$CONFIG_FILE" 2>/dev/null | head -n 1 | sed 's/[[:space:]]*$//'
	}
	agent_name="$(config_value agent_name)"
	agent_bouquet="$(config_value bouquet)"
	shopt -s nullglob
	agent_invitations=(invitations/received/*_agent_*.yml invitations/received/*_agent_*.yaml)
	named=()
	[ -n "$agent_name" ] && named=(invitations/received/*_agent_"$agent_name".yml invitations/received/*_agent_"$agent_name".yaml)
	shopt -u nullglob
	if [ "${#named[@]}" -gt 1 ] && [ -f "invitations/received/${agent_bouquet}_agent_${agent_name}.yml" ]; then
		named=("invitations/received/${agent_bouquet}_agent_${agent_name}.yml")
	fi
	if [ "${#named[@]}" -eq 1 ]; then
		AGENT_INVITATION="${named[0]}"
	elif [ "${#named[@]}" -gt 1 ]; then
		echo "ERROR: several invitations of $agent_name in invitations/received (${named[*]}): keep one, or set PYBISCUS_AGENT_INVITATION" >&2
		exit 1
	elif [ "${#agent_invitations[@]}" -eq 1 ]; then
		AGENT_INVITATION="${agent_invitations[0]}"
		echo "🎫 the only agent invitation of invitations/received, ${AGENT_INVITATION}: its name and role prevail over ${CONFIG_FILE}'s" >&2
	elif [ "${#agent_invitations[@]}" -gt 1 ]; then
		echo "ERROR: none of the agent invitations of invitations/received (${agent_invitations[*]}) is named after ${agent_name:-this agent}: keep its own, or set PYBISCUS_AGENT_INVITATION" >&2
		exit 1
	fi
fi
