#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)
PYBISCUS_IMAGE=$(pybiscus_image local)

    #--user $uid:$gid \

$CONTAINER_ENGINE run \
    -t \
    --rm \
    --name "pybiscus-local-train" \
    --network=host \
    --gpus device=1 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --shm-size 50G \
    $PYBISCUS_IMAGE local train-config configs/cifar10_cnn/localhost/without_ssl/train.yml

