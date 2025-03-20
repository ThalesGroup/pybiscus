#!/usr/bin/bash

CONTAINER_ENGINE=$(container_engine)

echo "[container using ${CONTAINER_ENGINE}] ubuntu root access to pybiscus volumes"

$CONTAINER_ENGINE run \
    -it \
    --rm \
    --name "ubuntu-with-pybiscus-volumes"       \
    -v ${PWD}/datasets/:/pybiscus/datasets/     \
    -v ${PWD}/experiments:/pybiscus/experiments \
    -v ${PWD}/configs:/pybiscus/configs         \
    ubuntu:latest /usr/bin/bash
