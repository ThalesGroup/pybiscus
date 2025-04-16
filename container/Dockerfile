ARG http_proxy
ARG https_proxy
ARG no_proxy

ARG CUDA_VERSION="11.7.1-cudnn8"
ARG UBUNTU_VERSION="20.04"

ARG PYTHON_VERSION="3.12"

ARG BASE_REGISTRY="docker.io/nvidia"
ARG BASE_IMAGE="cuda"
ARG BASE_IMAGE_TAG="${CUDA_VERSION}-devel-ubuntu${UBUNTU_VERSION}"
ARG APP_DIR=/app

##############################################################################

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG}

# Install curl
RUN apt-get update \
	&& DEBIAN_FRONTEND=noninteractive \
	&& apt-get install -q -y --no-install-recommends \
	curl \
	tini \
	&& rm -rf /var/lib/apt/lists/* /var/log/dpkg.log

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
#RUN mv /root/.local/bin/uv /usr/local/bin && chmod a+x /usr/local/bin/uv 
#RUN mkdir -p /app/.cache/uv && chmod -R a+rwr /app/.cache/uv
#RUN chmod -R a+rwx /root

# Add $HOME/.local directory to PATH
ENV PATH="/root/.local/bin:$PATH"

# Define APP_DIR env var
ENV APP_DIR=${APP_DIR}
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Create working dir
#WORKDIR ${APP_DIR}
WORKDIR /app

RUN mkdir datasets
COPY pybiscus           ./pybiscus
COPY bin           ./bin
COPY certificates/ ./certificates
COPY configs/      ./configs

# Install python and pin the current used version
RUN uv python install 3.12
RUN uv python pin 3.12

# Copy pyproject.toml iand uv.lock files and install dependancies
COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --frozen

#RUN chmod 777 /app

# Command to keep the container running indefinitely
#CMD ["bash", "-c", "while true; do echo 'Running...'; sleep 30; done"]

#ENTRYPOINT ["/usr/bin/tini", "-g", "-s", "--", "${APP_DIR}/bin/pybiscus"]
ENTRYPOINT ["/usr/bin/tini", "-g", "-s", "--", "/app/bin/pybiscus_in_container"]

# See https://github.com/opencontainers/image-spec/blob/main/annotations.md
ARG LABEL_BASE_NAME="${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG}"
LABEL org.opencontainers.image.base.name="${LABEL_BASE_NAME}"

