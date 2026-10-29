#!/usr/bin/bash

export SERVER_NAME="localhost"
export SERVER_PORT="3333"
export SERVER_ADDRESS="${SERVER_NAME}:${SERVER_PORT}"
export SERVICE="[::]:${SERVER_PORT}"

PYBISCUS_CONF_PATH=configs/onnx_eval

# the file each site evaluates (prepare.sh publishes it) and its SHA-256: on several machines the
# organiser gives the hash and each site sets it; hashing the local file here only suits one machine
export PYBISCUS_ONNX_MODEL="${PYBISCUS_ONNX_MODEL:-$PWD/experiments/published/mnist_cnn.onnx}"
if [ -z "${PYBISCUS_ONNX_SHA256:-}" ] && [ -f "$PYBISCUS_ONNX_MODEL" ]; then
    PYBISCUS_ONNX_SHA256="$(sha256sum "$PYBISCUS_ONNX_MODEL" | cut -d' ' -f1)"
    export PYBISCUS_ONNX_SHA256
fi
