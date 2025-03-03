#!/usr/bin/bash

IMAGE_NAME=$(pybiscus_node_image)

echo "Building image: ${IMAGE_NAME}"

# create the paroma container
#podman build \
$(container_engine) build \
	 -f container/Dockerfile_node \
	 --build-arg http_proxy=$HTTP_PROXY \
	 --build-arg https_proxy=$HTTPS_PROXY \
	 --build-arg no_proxy=$NO_PROXY \
	 .. \
	 -t $IMAGE_NAME

