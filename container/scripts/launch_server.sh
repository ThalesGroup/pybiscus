docker run \
    -t \
    --rm \
    --name "hibiscus-server" \
    --gpus device=0 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    --net-alias server \
    --user $uid:$gid \
    --shm-size 50G \
    hibiscus:app.v0.3.2 server launch-config configs/server.yml