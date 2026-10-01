#!/usr/bin/bash

# the clients reach the server at this name: localhost for a session on one machine, the server's
# name or address otherwise
export SERVER_NAME="localhost"
export SERVER_PORT="3333"

# passed to the clients as --server-address (it replaces flower_client.server_address)
export SERVER_ADDRESS="${SERVER_NAME}:${SERVER_PORT}"

# passed to the server as --server-listen-address (it replaces flower_server.listen_address):
# every interface, IPv6 and IPv4
export SERVICE="[::]:${SERVER_PORT}"

PYBISCUS_CONF_PATH=configs/cifar10_cnn/distributed/without_ssl

