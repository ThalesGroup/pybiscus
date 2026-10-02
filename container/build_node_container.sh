#!/usr/bin/bash

# the Dockerfile copies paths of the repository root, wherever the script is called from
REPO="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
export PATH="$REPO/bin:$PATH"
cd "$REPO" || exit 1

IMAGE_NAME=$(pybiscus_node_image)

echo "Building image: ${IMAGE_NAME}"

# create the container
$(container_engine) build \
	 -f container/Dockerfile_node \
	 --build-arg http_proxy=$HTTP_PROXY \
	 --build-arg https_proxy=$HTTPS_PROXY \
	 --build-arg no_proxy=$NO_PROXY \
	 . \
	 -t $IMAGE_NAME

