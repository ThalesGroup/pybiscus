# Containers

Shells are provided for containers management. They rely on podman (first choice) or docker,
whichever `bin/container_engine` finds first.

## Build

Two images, built from the repository root, about 6.3 GB each: Ubuntu 24.04 and PyTorch, whose
wheels carry their own CUDA libraries (no CUDA base image: the host's NVIDIA driver is enough):

```bash
./container/build_pybiscus_container.sh   # the pybiscus command (server, client, local)
./container/build_node_container.sh       # the agent (pybiscus_agent), for sessions
```

The image names come from `bin/pybiscus_image` and `bin/pybiscus_node_image`: `pybiscus:<version>`
and `pybiscus-agent:<version>`, the version being the one of `pyproject.toml` (override a name
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
- The scripts give the containers the GPU `PYBISCUS_GPU`: a device number (`0` by default), `all`,
  or `none` to run on CPU. `bin/container_gpu` writes the option of the engine: `--gpus device=<n>`
  with docker, `--device nvidia.com/gpu=<n>` with podman (which reads `--gpus device=0` as a CDI
  device that does not exist), `all` when the CDI description has only that one, as under WSL.

### The GPU in a container

The host needs its NVIDIA driver and the NVIDIA Container Toolkit (`nvidia-container-toolkit`
package, NVIDIA's apt repository); no CUDA toolkit. For podman, generate its CDI description once,
and again after a driver update:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nvidia-ctk cdi list            # nvidia.com/gpu=0 ... (WSL2: nvidia.com/gpu=all only)
```

Under WSL2, the driver is Windows': do not install a Linux NVIDIA driver in the distribution, it
would hide the GPU that WSL exposes (`/dev/dxg`, `/usr/lib/wsl/lib`). `SMOKE_GPU=1
launch/ci/smoke.sh container-run` runs the smoke session in containers on the GPU.

`launch/agent/container/500{0,1,2}.sh` start the agents in containers, for a session driven by
the session manager (see [Session using the manager](sessionmanager.md)). Run them from the
repository root: they mount its `datasets/` and `experiments/`, where the runs the agent launches
read their data and write their reports. Each agent keeps its tokens and settings in
`.pybiscus-cache/container-agent-<port>/`, so that a new container keeps its registration link.

## In a Kubernetes cluster

`launch/k8s/mnist_cnn/` runs the mnist demo (`configs/mnist_cnn/distributed/`) in a cluster, in
the CLI mode: the Flower server and two clients as Jobs. Tested on k3s, one node, on CPU.

Once, import the image into the cluster: k3s runs its own containerd, which does not see the images
of podman or docker (the manifests use `imagePullPolicy: Never`). k3s's `kubectl` reads
`/etc/rancher/k3s/k3s.yaml`, readable by root only: give yourself a copy.

```bash
podman save localhost/pybiscus:0.17.0 | sudo k3s ctr images import -
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config && sudo chown $USER ~/.kube/config
```

Then, from anywhere:

```bash
NUM_ROUNDS=2 ./launch/k8s/mnist_cnn/run.sh            # NUM_ROUNDS: 10 by default
kubectl -n pybiscus logs -f job/flower-server
./launch/k8s/mnist_cnn/stop.sh                        # removes the namespace, keeps the reports
```

- `run.sh` creates the namespace `pybiscus` (`NAMESPACE`), a ConfigMap from the three
  configurations, then `server.yaml` and `client.yaml` (once per client), whose placeholders it
  fills: paths of the repository, image (`K8S_IMAGE`, `localhost/pybiscus:<version>` by default),
  rounds, user. Running it again replaces the Jobs of the previous run.
- The server is a Job, not a Deployment, which would restart it after its last round. The clients
  reach it at the Service `flower-server:3333`; each waits for it (an init container) since a
  Flower client finding no server stops at once.
- The repository's `datasets/` and `experiments/` are mounted (`hostPath`, one node; on several
  nodes, a PersistentVolumeClaim). The reports land in `experiments/` as with the other launches,
  given back to the user who ran `run.sh` (the image runs as root).
- **A NetworkPolicy lets only the clients' pods reach the server's port**: in the CLI mode the
  Flower server does not authenticate its clients ([known limits](security.md#known-limits)).
  It selects the pods by their label `pybiscus.role: flower-client`, so whoever may create pods in
  the namespace may join a round: restrict that right (RBAC). k3s enforces NetworkPolicies; another
  cluster needs a network plugin that does (Calico, Cilium...).

A session of the manager in a cluster is possible but heavier (see
[usage scenarios](usage-scenarios.md#several-machines-on-a-closed-network)); no manifest is provided
for it.

## Behind a proxy

Define and export, according to your system, `no_proxy`, `http_proxy`, `https_proxy` or
`NO_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY`: the build and launch scripts pass them to the containers.
