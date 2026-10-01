#!/usr/bin/bash

# local training, without federation: a baseline for the federated runs
uv run python pybiscus/main.py local train-config configs/cifar10_cnn/local/train.yml
