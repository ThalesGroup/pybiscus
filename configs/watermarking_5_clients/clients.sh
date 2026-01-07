#!/bin/bash

# Script to launch 5 clients with their respective configurations

uv run python pybiscus/main.py client launch configs/deeplog_watermarking/setting_5_clients/cortaix-labs-01.yml &
uv run python pybiscus/main.py client launch configs/deeplog_watermarking/setting_5_clients/cortaix-labs-02.yml &
uv run python pybiscus/main.py client launch configs/deeplog_watermarking/setting_5_clients/cortaix-labs-03.yml &
uv run python pybiscus/main.py client launch configs/deeplog_watermarking/setting_5_clients/cortaix-labs-04.yml &
uv run python pybiscus/main.py client launch configs/deeplog_watermarking/setting_5_clients/cortaix-labs-05.yml
# Wait for all background processes to finish
wait