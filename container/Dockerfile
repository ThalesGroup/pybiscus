ARG http_proxy
ARG https_proxy
ARG no_proxy

ARG CUDA_VERSION="11.7.1-cudnn8"
ARG UBUNTU_VERSION="20.04"

ARG BASE_REGISTRY="docker.io/nvidia"
ARG BASE_IMAGE="cuda"
ARG BASE_IMAGE_TAG="${CUDA_VERSION}-devel-ubuntu${UBUNTU_VERSION}"
ARG HOME=/app/

##############################################################################

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG} AS base

FROM base as builder

ARG HOME
ARG ENCODING=C.UTF-8
ARG PYENV_ROOT="/pyenv/"

ENV LANG=${ENCODING} \
    LC_ALL=${ENCODING} \
    PYENV_ROOT="${PYENV_ROOT}"
ENV PIPENV_PYTHON="${PYENV_ROOT}/shims/python" \
    PATH="${PYENV_ROOT}/bin/:${PYENV_ROOT}/shims/:${HOME}/.local/bin:${PATH}" \
    HOME="${HOME}"

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -q -y --no-install-recommends \
    ca-certificates libglib2.0-0  libsm6 libxext6 libxrender1 mercurial \
    openssh-client procps subversion curl make build-essential libssl-dev \
    zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev \
    liblzma-dev bzip2 git curl \
  && apt-get -qq -y autoremove \
  && apt-get autoclean \
  && rm -rf /var/lib/apt/lists/* /var/log/dpkg.log

ARG PYTHON_VERSION="3.9.12"

RUN curl -sSL https://pyenv.run | sh - \
  && pyenv install $PYTHON_VERSION \
  && pyenv global $PYTHON_VERSION \
  && pyenv rehash \
  && find $PYENV_ROOT/versions -type d '(' -name '__pycache__' -o -name 'test' -o -name 'tests' ')' -exec rm -rfv '{}' + \
  && find $PYENV_ROOT/versions -type f '(' -name '*.py[co]' -o -name '*.exe' ')' -exec rm -fv '{}' + \
  && chmod -R 755 $PYENV_ROOT

WORKDIR "${HOME}/app"

# RUN curl -sSL  https://install.python-poetry.org | python - \
#  && poetry config virtualenvs.create false

# COPY pyproject.toml poetry.lock ./
# RUN poetry export -f requirements.txt -o requirements.txt --without-hashes \
#  && pip install --requirement requirements.txt

# RUN ls -alh dist/
COPY ./ ./
# RUN poetry build
RUN pip install -U pip wheel setuptools
RUN pip install --no-cache-dir pybiscus-0.3.2-py3-none-any.whl

##############################################################################

FROM base

ARG HOME

ARG ENCODING=C.UTF-8
ARG PYENV_ROOT="/pyenv/"

ENV LANG=${ENCODING} \
    LC_ALL=${ENCODING} \
    PYENV_ROOT="${PYENV_ROOT}"
ENV PIPENV_PYTHON="${PYENV_ROOT}/shims/python" \
    PATH="${PYENV_ROOT}/bin/:${PYENV_ROOT}/shims/:${HOME}/.local/bin:${PATH}" \
    HOME="${HOME}"

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -q -y --no-install-recommends \
    tini \
  && apt-get -qq -y autoremove \
  && apt-get autoclean \
  && rm -rf /var/lib/apt/lists/* /var/log/dpkg.log

COPY --from=builder $PYENV_ROOT $PYENV_ROOT

RUN adduser --disabled-password --home $HOME --gecos "" appuser

WORKDIR $HOME
USER appuser

ENTRYPOINT ["/usr/bin/tini", "-g", "-s", "--", "pybiscus_app"]

# See https://github.com/opencontainers/image-spec/blob/main/annotations.md
ARG LABEL_BASE_NAME="${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_IMAGE_TAG}"
LABEL org.opencontainers.image.base.name="${LABEL_BASE_NAME}"
