ARG http_proxy
ARG https_proxy
ARG no_proxy

ARG PYTHON_VERSION="3.12"

# a plain Ubuntu: torch's wheels carry their own CUDA libraries (the nvidia-* packages of uv.lock)
# and need only the host's driver; a CUDA base image put a second, unused CUDA in the image (7.5 GB)
ARG BASE_REGISTRY="docker.io/library"
ARG BASE_IMAGE="ubuntu"
ARG BASE_IMAGE_TAG="24.04"
ARG APP_DIR=/app

##############################################################################

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG}

# Install curl
RUN apt-get update \
	&& DEBIAN_FRONTEND=noninteractive \
	&& apt-get install -q -y --no-install-recommends \
	ca-certificates \
	curl \
	tini \
	&& rm -rf /var/lib/apt/lists/* /var/log/dpkg.log

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
#RUN mv /root/.local/bin/uv /usr/local/bin && chmod a+x /usr/local/bin/uv 
#RUN mkdir -p /app/.cache/uv && chmod -R a+rwr /app/.cache/uv
#RUN chmod -R a+rwx /root

# as the CUDA images set them: the NVIDIA Container Toolkit (--gpus) reads them to mount the driver
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Add $HOME/.local directory to PATH
ENV PATH="/root/.local/bin:$PATH"

# Define APP_DIR env var
ENV APP_DIR=${APP_DIR}
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Create working dir
#WORKDIR ${APP_DIR}
WORKDIR /app

RUN mkdir datasets
COPY pybiscus                  ./pybiscus
COPY pybiscus-plugins          ./pybiscus-plugins
COPY pybiscus-plugins-hierarchical ./pybiscus-plugins-hierarchical
COPY pybiscus-plugins-privacy-evaluation ./pybiscus-plugins-privacy-evaluation
COPY bin                       ./bin
COPY certificates/             ./certificates
COPY configs/                  ./configs

# Install python and pin the current used version
RUN uv python install 3.12
RUN uv python pin 3.12

# Copy pyproject.toml iand uv.lock files and install dependancies
COPY pyproject.toml .
COPY uv.lock .
# every extra: the image carries every plugin directory, the privacy evaluation's analyser included
RUN uv sync --frozen --all-extras --no-dev
# a plugin whose requirements the image lacks fails the build, not a run
RUN PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml:pybiscus-plugins-privacy-evaluation/plugins-conf.yml \
    uv run --frozen --no-sync python pybiscus/main.py plugins deps

#RUN chmod 777 /app

# Command to keep the container running indefinitely
#CMD ["bash", "-c", "while true; do echo 'Running...'; sleep 30; done"]

#ENTRYPOINT ["/usr/bin/tini", "-g", "-s", "--", "${APP_DIR}/bin/pybiscus"]
ENTRYPOINT ["/usr/bin/tini", "-g", "-s", "--", "/app/bin/pybiscus_in_container"]

# See https://github.com/opencontainers/image-spec/blob/main/annotations.md
ARG LABEL_BASE_NAME="${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG}"
LABEL org.opencontainers.image.base.name="${LABEL_BASE_NAME}"

