## Docker

To build the image (which is quite heavy as of now), do the following
```bash
cd container
docker build . -t pybiscus:app.v0.5.0
```



If you are working under a proxy, you might need to add some argument for the buid

```bash
cd container
docker build \
--build-arg http_proxy=$HTTP_PROXY \
--build-arg https_proxy=$HTTPS_PROXY \
--build-arg no_proxy=$NO_PROXY \
. -t pybiscus:app.v0.5.0
```

Then, again only if you have to go through a proxy for internet access, then to download the data the different containers will need and internet access.
So you need to set the file `~/.docker/config.json` with the proxy config

For the client to be able to communicate with the server you need to add "server"
to ne noProxy config.

```json
{
        "proxies":{
                "default":{
                        "httpsProxy": "your_httpsProxy",
                        "httpProxy": "your_httpProxy",
                        "noProxy": "your_noProxy,server",
                }
        }
}
```

and voila! The docker image is aimed at running only the pybiscus_app itself. In order to facilitate the use of docker (which can be quite verbose), some scripts are available in container/scripts. To launch a local training, you just need to update `container/scripts/launch_local_train.sh` and `container/configs/local_train.yml` according to where are located your datasets and such. Then, simply run
```bash
bash container/scripts/launch_local_train.sh
```

It is as simple as running
```bash
docker run -t --gpus device=(some_device) -v "$(pwd)":/app/datasets pybiscus:app --help
```

to get the help of the app. The short version is, `docker run -t pybiscus:app.v0.5.0` is equivalent to running `pybiscus_app`. As for the app itself, the docker image can launch either client, server or local components.

To launch a "true" Federated learning, you need first to create a docker network for the containers to communicate:
```bash
docker network create federated
```

then
```bash
bash container/scripts/launch_server.sh
```

followed by (in other terminal)
```bash
bash container/scripts/launch_client_1.sh
```
and
```bash
bash container/scripts/launch_client_2.sh
```
