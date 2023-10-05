docker run \
    -t \
    --rm \
    --name "hibiscus-local-train" \
    --gpus device=3 \
    -v ${PWD}/datasets/:/app/datasets/ \
    -v ${PWD}/experiments:/app/experiments \
    -v ${PWD}/container/configs:/app/configs \
    --user $uid:$gid \
    --shm-size 50G \
    hibiscus:app.v0.3.2 local train-config configs/local_train.yml