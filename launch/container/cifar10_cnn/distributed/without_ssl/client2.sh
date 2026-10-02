#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image client)

# passed as --server-address below (it replaces flower_client.server_address); the client runs on
# the host network: the server's published port is on this machine, or give the server's name
export SERVER_ADDRESS="${SERVER_ADDRESS:-localhost:3333}"

echo "[container] client2 -> server : ${SERVER_ADDRESS}"

uid=$(id -u)  # current user
gid=$(id -g)  # current group

    #--user $uid:$gid                         \

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-client-2"               \
    --network=host \
    --gpus device=0                          \
    -v ${PWD}/datasets/:/app/datasets/       \
    -v ${PWD}/experiments:/app/experiments   \
    -v ${PWD}/configs:/app/configs           \
    -e no_proxy=$no_proxy                    \
    -e NO_PROXY=$NO_PROXY                    \
    -e http_proxy=$http_proxy                \
    -e https_proxy=$https_proxy              \
    -e HTTP_PROXY=$HTTP_PROXY                \
    -e HTTPS_PROXY=$HTTPS_PROXY              \
    --shm-size 50G                           \
    $PYBISCUS_IMAGE client launch configs/cifar10_cnn/distributed/without_ssl/client_2.yml --server-address "$SERVER_ADDRESS"

