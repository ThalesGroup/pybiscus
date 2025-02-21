#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image server)

# pybiscus configuration override (container internal)
DOCKER_SERVER_LISTEN_IP="0.0.0.0"
DOCKER_SERVER_PORT="3333"
export DOCKER_SERVER_INTERFACE="$DOCKER_SERVER_LISTEN_IP:$DOCKER_SERVER_PORT"

echo "[container] server listening in container on : ${DOCKER_SERVER_INTERFACE}"

# pybiscus configuration override (public)
PUBLIC_SERVER_LISTEN_IP="0.0.0.0"
PUBLIC_SERVER_PORT="3333"
export PUBLIC_SERVER_INTERFACE="$PUBLIC_SERVER_LISTEN_IP:$PUBLIC_SERVER_PORT"
echo "[container] server listening on internet on : ${PUBLIC_SERVER_INTERFACE}"

uid=$(id -u)  # current user
gid=$(id -g)  # current group

    #--user $uid:$gid                         \

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-server"                 \
    --gpus device=1                          \
    -v ${PWD}/datasets/:/app/datasets/       \
    -v ${PWD}/experiments:/app/experiments   \
    -v ${PWD}/configs:/app/configs           \
    -v ${PWD}/certificates:/app/certificates \
    -e SERVER_ADDRESS="$DOCKER_SERVER_INTERFACE" \
    -e no_proxy=$no_proxy                    \
    -e NO_PROXY=$NO_PROXY                    \
    -e http_proxy=$http_proxy                \
    -e https_proxy=$https_proxy              \
    -e HTTP_PROXY=$HTTP_PROXY                \
    -e HTTPS_PROXY=$HTTPS_PROXY              \
    -p "${PUBLIC_SERVER_INTERFACE}:${DOCKER_SERVER_PORT}" \
    --shm-size 50G                           \
    $PYBISCUS_IMAGE server launch configs/cifar10_cnn/distributed/ssl/server.yml

