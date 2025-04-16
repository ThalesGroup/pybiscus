#!/usr/bin/bash

source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/common.sh"

echo "[uv] client1 -> server : ${SERVER_ADDRESS}"

uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_1.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_2.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_3.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_4.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_5.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_6.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_7.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_8.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_9.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_10.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_11.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_12.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_13.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_14.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_15.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_16.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_17.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_18.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_19.yml &
uv run python pybiscus/main.py client launch ${PYBISCUS_CONF_PATH}/client_20.yml &

