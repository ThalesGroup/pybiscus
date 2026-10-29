#!/usr/bin/bash

# publishes the model of the last session (launch/uv/mnist_cnn/distributed exports it as one file)
# as the file the evaluation sessions read
source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"

source_model="${1:-experiments/current/model.onnx}"
if [ ! -f "$source_model" ]; then
    echo "no $source_model: run launch/uv/mnist_cnn/distributed first (server.sh, client1.sh, client2.sh)" >&2
    exit 1
fi
mkdir -p "$(dirname "$PYBISCUS_ONNX_MODEL")"
cp "$source_model" "$PYBISCUS_ONNX_MODEL"
echo "published $PYBISCUS_ONNX_MODEL"
echo "sha256    $(sha256sum "$PYBISCUS_ONNX_MODEL" | cut -d' ' -f1)"
