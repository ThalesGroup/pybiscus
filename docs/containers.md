# Containers

Shells are provided for containers management. They rely on podman (first choice) or docker,
whichever `bin/container_engine` finds first.

## Build

Two images, built from the repository root (each is heavy: PyTorch with CUDA):

```bash
./container/build_pybiscus_container.sh   # the pybiscus command (server, client, local)
./container/build_node_container.sh       # the agent (pybiscus_agent), for sessions
```

The image names come from `bin/pybiscus_image` and `bin/pybiscus_node_image` (override them
with `PYBISCUS_IMAGE`).

## A federated session in containers

`launch/container/cifar10_cnn/distributed/without_ssl/` runs the cifar10 demo
(`configs/cifar10_cnn/distributed/without_ssl/`), from the repository root, in three terminals:

```bash
./launch/container/cifar10_cnn/distributed/without_ssl/server.sh
./launch/container/cifar10_cnn/distributed/without_ssl/client1.sh
./launch/container/cifar10_cnn/distributed/without_ssl/client2.sh
```

- The repository's `datasets/`, `experiments/` and `configs/` are mounted into the containers.
- The server listens on every interface of its container (`--server-listen-address 0.0.0.0:3333`)
  and its port 3333 is published on the host.
- The clients run on the host network and reach the server at `SERVER_ADDRESS` (`localhost:3333`
  by default; give the server's name when it runs on another machine).
- The scripts reserve the GPU with `--gpus device=0`: change it to the device of your machine (or
  remove it to run on CPU).

`launch/agent/container/500{0,1,2}.sh` start the agents in containers, for a session driven by
the session manager (see [Session using the manager](sessionmanager.md)).

## Behind a proxy

Define and export, according to your system, `no_proxy`, `http_proxy`, `https_proxy` or
`NO_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY`: the build and launch scripts pass them to the containers.
