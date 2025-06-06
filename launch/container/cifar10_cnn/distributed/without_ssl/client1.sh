#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image client)

#export SERVER_ADDRESS="server-fqdn:3333"
export SERVER_ADDRESS="$(hostname):3333"

echo "[container] client1 -> server : ${SERVER_ADDRESS}"

uid=$(id -u)  # current user
gid=$(id -g)  # current group

    #--user $uid:$gid                         \
   
$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-client-1"               \
    --network=host \
    --gpus device=1                          \
    -v ${PWD}/datasets/:/app/datasets/       \
    -v ${PWD}/experiments:/app/experiments   \
    -v ${PWD}/configs:/app/configs           \
    -e SERVER_ADDRESS="$SERVER_ADDRESS"      \
    -e no_proxy=$no_proxy                    \
    -e NO_PROXY=$NO_PROXY                    \
    -e http_proxy=$http_proxy                \
    -e https_proxy=$https_proxy              \
    -e HTTP_PROXY=$HTTP_PROXY                \
    -e HTTPS_PROXY=$HTTPS_PROXY              \
    --shm-size 50G                           \
    $PYBISCUS_IMAGE client launch configs/cifar10_cnn/distributed/without_ssl/client_1.yml

