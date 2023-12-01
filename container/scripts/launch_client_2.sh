docker run \
    -t \
    --rm \
    --name "pybiscus-client-2" \
    --gpus device=2 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --net federated \
    --net-alias client-2 \
    --user $uid:$gid \
    --shm-size 50G \
    pybiscus:app.v0.5.0 client launch configs/client_2.yml
