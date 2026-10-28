#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_node_image)

# pybiscus configuration override (container internal)
DOCKER_SERVER_LISTEN_IP="0.0.0.0"
DOCKER_SERVER_PORT="3333"
export DOCKER_SERVER_INTERFACE="$DOCKER_SERVER_LISTEN_IP:$DOCKER_SERVER_PORT"

echo "[container] server listening in container on : ${DOCKER_SERVER_INTERFACE}"

# pybiscus configuration override (public)
PUBLIC_SERVER_LISTEN_IP="0.0.0.0"
PUBLIC_SERVER_PORT="3331"
export PUBLIC_SERVER_INTERFACE="$PUBLIC_SERVER_LISTEN_IP:$PUBLIC_SERVER_PORT"
echo "[container] server listening on internet on : ${PUBLIC_SERVER_INTERFACE}"

DOCKER_REST_PORT="5000"
PUBLIC_REST_PORT="5001"
echo "[container] agent listening on internet on : ${PUBLIC_REST_PORT}"

# the runs the agent launches read the data and write their reports there; podman refuses to mount
# a missing directory
mkdir -p experiments
# the agent's tokens and settings survive the container; one cache per container, since inside
# every agent listens on 5000 and the cache names its files by that port
AGENT_CACHE="${PWD}/.pybiscus-cache/container-agent-${PUBLIC_REST_PORT}"
mkdir -p "$AGENT_CACHE"

uid=$(id -u)  # current user
gid=$(id -g)  # current group
    # --user $uid:$gid                         \

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-agent-$PUBLIC_REST_PORT" \
    $(container_gpu)                         \
    -v ${PWD}/datasets/:/app/datasets/       \
    -v ${PWD}/experiments:/app/experiments   \
    -v "$AGENT_CACHE":/app/.pybiscus-cache   \
    -e SERVICE="$DOCKER_SERVER_INTERFACE"    \
    -e no_proxy=$no_proxy                    \
    -e NO_PROXY=$NO_PROXY                    \
    -e http_proxy=$http_proxy                \
    -e https_proxy=$https_proxy              \
    -e HTTP_PROXY=$HTTP_PROXY                \
    -e HTTPS_PROXY=$HTTPS_PROXY              \
    -p "${PUBLIC_SERVER_PORT}:${DOCKER_SERVER_PORT}" \
    -p "${PUBLIC_REST_PORT}:${DOCKER_REST_PORT}" \
    --shm-size 50G                           \
    $PYBISCUS_IMAGE
