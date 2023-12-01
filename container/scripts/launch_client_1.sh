docker run \
    -t \
    --rm \
    --name "pybiscus-client-1" \
    --gpus device=1 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    --net-alias client-1 \
    --user $uid:$gid \
    --shm-size 50G \
    pybiscus:app.v0.4.0 client launch-config configs/client_1.yml
