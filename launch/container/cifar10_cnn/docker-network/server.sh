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
    --net-alias server \
    --user $uid:$gid \
    --shm-size 50G \
    $(PYBISCUS_IMAGE) server launch-config configs/docker-network/cifar/server.yml

