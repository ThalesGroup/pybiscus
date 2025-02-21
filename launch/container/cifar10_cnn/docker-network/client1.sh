#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image client)

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-client-1" \
    --gpus device=1 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    --net-alias client-1 \
    --user $uid:$gid \
    --shm-size 50G \
    $(PYBISCUS_IMAGE) client launch-config configs/docker-network/cifar/client_1.yml

