docker run \
    -t \
    --rm \
    --name "pybiscus-server" \
    --gpus device=0 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    --net-alias server \
    --user $uid:$gid \
    --shm-size 50G \
    pybiscus:app.v0.4.0 server launch-config configs/server.yml