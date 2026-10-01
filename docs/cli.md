
# Command Line Interface

Install Pybiscus first ([Getting started](getting_started.md#installation)), then, from the
repository root:

```bash
pybiscus --help
```

The `pybiscus` command has four groups of commands:
- `server`: `launch` a Flower server, or `check` its configuration;
- `client`: `launch` a client, or `check` its configuration;
- `local`: `train-config`, a training on one site's data without federation, as a baseline;
- `data`: `partition`, how the training data is shared between the clients (`--export` writes
  each client's indices).

## A federated session

A server and any number of clients, each in its own process, each with its configuration file
(examples in `configs/`):

```bash
pybiscus server check  configs/cifar10_cnn/distributed/without_ssl/server.yml
pybiscus server launch configs/cifar10_cnn/distributed/without_ssl/server.yml
pybiscus client launch configs/cifar10_cnn/distributed/without_ssl/client_1.yml
pybiscus client launch configs/cifar10_cnn/distributed/without_ssl/client_2.yml
```

`check` validates a configuration against its Pydantic models without running anything. Options
replace some values of the configuration: `--server-listen-address`, `--num-rounds`,
`--weights-path` (initial weights) for the server; `--server-address`, `--cid`, `--root-dir` for a
client.

The scripts of `launch/uv/` run the demos, one terminal per process:

```bash
./launch/uv/cifar10_cnn/distributed/without_ssl/server.sh
./launch/uv/cifar10_cnn/distributed/without_ssl/client1.sh
./launch/uv/cifar10_cnn/distributed/without_ssl/client2.sh
```

`common.sh` in each directory sets the address the clients reach the server at (`localhost` for a
session on one machine) and the address the server listens on; the scripts pass them as options.
`launch/uv/mnist_cnn/distributed/` runs the mnist demo the same way.

## Encrypting the Flower traffic (SSL)

1. Generate a certificate authority and the server's certificate, from `certificates/` (adjust
   `set_env.sh` first: number of clients, names of the organisation):

   ```bash
   cd certificates && ./gen_from_env.sh && cd ..
   ```

   The server's certificate is valid for the machine's name, `localhost`, `127.0.0.1` and `::1`:
   the clients must reach the server at one of them. Add other names or addresses with
   `SERVER_SAN` (for instance `SERVER_SAN="DNS:server.example.org,IP:10.0.0.5"`).

2. Run the demo of `configs/cifar10_cnn/distributed/ssl/`: the server's `flower_server.ssl` gives
   the CA, its certificate and its key, each client's `flower_client.ssl` turns encryption on
   (`secure_cnx: true`) and gives the CA to check the server with.

   ```bash
   ./launch/uv/cifar10_cnn/distributed/ssl/server.sh
   ./launch/uv/cifar10_cnn/distributed/ssl/client1.sh
   ./launch/uv/cifar10_cnn/distributed/ssl/client2.sh
   ```

The server logs `SSL is enabled` when it starts.

## Local training

The same model on one site's data, without federation (Lightning's `Trainer`, whose arguments go
under `trainer:`):

```bash
pybiscus local train-config configs/mnist_cnn/local/train.yml
./launch/uv/cifar10_cnn/local/train.sh
```

The results go to `experiments/local/lightning_logs/` (TensorBoard events, checkpoints, the
configuration used).
