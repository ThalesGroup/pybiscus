# Containers

Shells are provided for containers management.
They rely on the presence of the tools : podman (first choice) or docker .

## Build

To build the image (which is quite heavy as of now), do the following
```bash
cd container
./build_pybiscus_container.sh
```



and voila! The image is aimed at running only the pybiscus application itself.

## Use

In order to facilitate the use of pybiscus, some scripts are available in $PYBISCUS_HOME/launch/ subdirectories. 

They refer to configuration files that are available in $PYBISCUS_HOME/config/ subdirectories. 

For instance, to launch a local training, you just need to update `configs/cifar10_cnn/localhost/without_ssl/train.yml` according to where are located your datasets and such.
Then, simply run
```bash
./launch/container/cifar10_cnn/localhost/train.sh
```


To launch a "local" Federated learning, you need first to create a docker network for the containers to communicate:
```bash
`./bin/container_engine` network create federated
```

then
```bash
./launch/container/cifar10_cnn/docker-network/server.sh
```

followed by (in other terminals : tmux is your friend)
```bash
./launch/container/cifar10_cnn/docker-network/client1.sh
```
and
```bash
./launch/container/cifar10_cnn/docker-network/client2.sh
```

## Docker behind a Proxy

If you are working behind a proxy, you might need to define and export environment variables corresponding to your system : 

no_proxy, http_proxy, https_proxy or NO_PROXY, HTTP_PROXY, HTTPS_PROXY 
as they are exported to your container in the launch scripts.
