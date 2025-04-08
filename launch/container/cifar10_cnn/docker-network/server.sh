#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image server)

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-server" \
    --gpus device=0 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    -e no_proxy=$no_proxy                    \
    -e NO_PROXY=$NO_PROXY                    \
    -e http_proxy=$http_proxy                \
    -e https_proxy=$https_proxy              \
    -e HTTP_PROXY=$HTTP_PROXY                \
    -e HTTPS_PROXY=$HTTPS_PROXY              \
    --net-alias server \
    --user $uid:$gid \
    --shm-size 50G \
    $(PYBISCUS_IMAGE) server launch-config configs/docker-network/cifar/server.yml

