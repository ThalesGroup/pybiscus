 #!/usr/bin/bash 

# the agents require the X-Pybiscus header on the requests that change something (CSRF), and
# their access token when they require one: kept where the agent was started (the repository root
# for launch/agent/cli)
TOKEN="${PYBISCUS_AGENT_TOKEN:-$(cat .pybiscus-cache/tokens/agent-5001 2>/dev/null)}"
curl -X POST -H "X-Pybiscus: 1" -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5001/client/config -F "file=@configs/toupload/client_1.yml"
curl -X POST -H "X-Pybiscus: 1" -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5001/client"
