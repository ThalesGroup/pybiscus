docker run \
    -t \
    --rm \
    --name "pybiscus-local-train" \
    --gpus device=3 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --user $uid:$gid \
    --shm-size 50G \
    pybiscus:app.v0.4.0 local train-config configs/local_train.yml
