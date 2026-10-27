#!/usr/bin/bash
# Builds an image of Pybiscus with a plugin directory of your own (container/Dockerfile_with_plugins):
#   container/build_container_with_plugins.sh <plugin directory> [image]      (default image: <directory>:<version>)
# The plugin directory holds its manifest plugins-conf.yml; it is the build context.

set -e
if [ -z "$1" ] || [ ! -f "$1/plugins-conf.yml" ]; then
    echo "usage: $0 <plugin directory holding plugins-conf.yml> [image]" >&2
    exit 2
fi
REPO="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
export PATH="$REPO/bin:$PATH"

PLUGINS_DIR="$(basename "$(realpath "$1")")"
CONTEXT="$(realpath "$1")"
BASE="$(pybiscus_image)"
IMAGE="${2:-${PLUGINS_DIR,,}:$(pybiscus_image | sed 's/.*://')}"

echo "Building image ${IMAGE} from ${BASE} with ${CONTEXT}"
$(container_engine) build \
    -f "$REPO/container/Dockerfile_with_plugins" \
    --build-arg PYBISCUS_IMAGE="$BASE" \
    --build-arg PLUGINS_DIR="$PLUGINS_DIR" \
    --build-arg http_proxy=$HTTP_PROXY \
    --build-arg https_proxy=$HTTPS_PROXY \
    --build-arg no_proxy=$NO_PROXY \
    -t "$IMAGE" \
    "$CONTEXT"
