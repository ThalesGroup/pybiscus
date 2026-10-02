#!/usr/bin/bash

# Smoke checks of a Pybiscus checkout, each step failing with a non-zero exit code:
#
#   launch/ci/smoke.sh [check] [run] [build] [container-run]     (default: check run)
#
#   check          every configuration of configs/ passes `server check` / `client check`
#   run            a short federated run (mnist demo, server + 2 clients, CPU)
#   build          the two container images
#   container-run  the same short run, in containers of the pybiscus image
#
# Environment: PYBISCUS_PYTHON (default: "uv run --project <repo> python"), SMOKE_WORK (work
# directory, default: a new temporary one, kept for its logs), SMOKE_ROUNDS (2),
# SMOKE_MAX_SAMPLES (2000), SMOKE_THREADS (2), SMOKE_TIMEOUT (seconds per run, 900).

REPO="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/../.." && pwd)"
PYTHON="${PYBISCUS_PYTHON:-uv run --project $REPO python}"
WORK="${SMOKE_WORK:-$(mktemp -d -t pybiscus-smoke.XXXXXX)}"
ROUNDS="${SMOKE_ROUNDS:-2}"
MAX_SAMPLES="${SMOKE_MAX_SAMPLES:-2000}"
THREADS="${SMOKE_THREADS:-2}"
TIMEOUT="${SMOKE_TIMEOUT:-900}"
DEMO="configs/mnist_cnn/distributed"

export PATH="$REPO/bin:$PATH"
mkdir -p "$WORK"

GROUPS_TO_KILL=()
CONTAINERS_TO_REMOVE=()

cleanup() {
    local group container
    for group in "${GROUPS_TO_KILL[@]}"; do
        kill -- "-$group" 2>/dev/null
    done
    for container in "${CONTAINERS_TO_REMOVE[@]}"; do
        "$(container_engine)" rm -f "$container" >/dev/null 2>&1
    done
}
trap cleanup EXIT

free_port() {
    $PYTHON -c 'import socket; s = socket.socket(); s.bind(("", 0)); print(s.getsockname()[1])'
}

wait_for_port() {
    local port="$1" waited=0
    until (exec 3<>"/dev/tcp/localhost/$port") 2>/dev/null; do
        sleep 2
        waited=$((waited + 2))
        [ "$waited" -ge 180 ] && return 1
    done
    return 0
}

wait_for_exit() {
    local pid="$1" limit="$2" waited=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 2
        waited=$((waited + 2))
        [ "$waited" -ge "$limit" ] && return 1
    done
    return 0
}

step_check() {
    local logs="$WORK/check" config kind log failed=0 checked=0
    mkdir -p "$logs"
    # configs/uploaded holds what the agents wrote at run time, not shipped configurations
    while IFS= read -r config; do
        if grep -q '^server_run:' "$REPO/$config"; then
            kind=server
        elif grep -q '^client_run:' "$REPO/$config"; then
            kind=client
        else
            echo "  skipped  $config (neither a server nor a client configuration: no check command)"
            continue
        fi
        log="$logs/$(echo "$config" | tr '/' '_').log"
        checked=$((checked + 1))
        if (cd "$REPO" && $PYTHON pybiscus/main.py "$kind" check "$config") >"$log" 2>&1; then
            echo "  ok       $config"
        else
            echo "  FAILED   $config ($kind check, see $log)"
            failed=$((failed + 1))
        fi
    done < <(cd "$REPO" && find configs -name '*.yml' -not -path 'configs/uploaded/*' | sort)
    echo "  $checked configuration(s) checked, $failed failed"
    [ "$failed" -eq 0 ]
}

# the experiments and logs of a run go to its own directory, never to the repository's
prepare_run_dir() {
    local dir="$1"
    mkdir -p "$dir/configs" "$dir/experiments" "$REPO/datasets"
    ln -sfn "$REPO/pybiscus-plugins" "$dir/pybiscus-plugins"
    ln -sfn "$REPO/pybiscus-plugins-conf.yml" "$dir/pybiscus-plugins-conf.yml"
    ln -sfn "$REPO/datasets" "$dir/datasets"
    $PYTHON "$REPO/launch/ci/smoke_configs.py" "$REPO/$DEMO" "$dir/configs" "$MAX_SAMPLES" "$THREADS"
}

judge_run() {
    local dir="$1" failed=0 name
    shift
    for name in server client_1 client_2; do
        if [ "$1" -ne 0 ]; then
            echo "  FAILED   $name exited with code $1 (see $dir/$name.log)"
            failed=1
        fi
        shift
        if grep -q 'Traceback (most recent call last)' "$dir/$name.log"; then
            echo "  FAILED   $name logged a traceback (see $dir/$name.log)"
            failed=1
        fi
    done
    if ! grep -q "\[ROUND $ROUNDS\]" "$dir/server.log"; then
        echo "  FAILED   the server did not reach round $ROUNDS (see $dir/server.log)"
        failed=1
    fi
    if [ -z "$(find "$dir/experiments" -name final_checkpoint.pt)" ]; then
        echo "  FAILED   no final checkpoint under $dir/experiments"
        failed=1
    fi
    [ "$failed" -eq 0 ] && echo "  ok       $ROUNDS rounds, server and 2 clients, logs in $dir"
    return "$failed"
}

step_run() {
    local dir="$WORK/run" port pids=() codes=() pid name
    prepare_run_dir "$dir" || return 1
    port="$(free_port)" || return 1
    cd "$dir" || return 1

    setsid $PYTHON "$REPO/pybiscus/main.py" server launch configs/server.yml \
        --num-rounds "$ROUNDS" --server-listen-address "[::]:$port" >server.log 2>&1 &
    pids+=("$!"); GROUPS_TO_KILL+=("$!")
    if ! wait_for_port "$port"; then
        echo "  FAILED   the server did not open its port $port (see $dir/server.log)"
        return 1
    fi
    for name in client_1 client_2; do
        setsid $PYTHON "$REPO/pybiscus/main.py" client launch "configs/$name.yml" \
            --server-address "localhost:$port" >"$name.log" 2>&1 &
        pids+=("$!"); GROUPS_TO_KILL+=("$!")
    done

    if ! wait_for_exit "${pids[0]}" "$TIMEOUT"; then
        echo "  the run exceeded $TIMEOUT s: stopped"
        kill -- "-${pids[0]}" 2>/dev/null
    fi
    for pid in "${pids[@]}"; do
        # a client outliving the server by more than a minute is stuck
        wait_for_exit "$pid" 60 || kill -- "-$pid" 2>/dev/null
        wait "$pid"
        codes+=("$?")
    done
    cd "$REPO" || return 1
    judge_run "$dir" "${codes[@]}"
}

step_build() {
    (cd "$REPO" && ./container/build_pybiscus_container.sh) || return 1
    (cd "$REPO" && ./container/build_node_container.sh) || return 1
}

step_container_run() {
    local dir="$WORK/container-run" engine image port pids=() codes=() pid name container
    engine="$(container_engine)" || return 1
    image="$(pybiscus_image)"
    prepare_run_dir "$dir" || return 1
    port="$(free_port)" || return 1

    # /app is the image's working directory, hence the configurations' root_dir
    local mounts=(-v "$REPO/datasets:/app/datasets" -v "$dir/experiments:/app/experiments"
                  -v "$dir/configs:/app/smoke-configs:ro")

    container="pybiscus-smoke-server-$$"
    CONTAINERS_TO_REMOVE+=("$container")
    "$engine" run --rm --name "$container" "${mounts[@]}" -p "$port:$port" \
        "$image" server launch smoke-configs/server.yml \
        --num-rounds "$ROUNDS" --server-listen-address "0.0.0.0:$port" >"$dir/server.log" 2>&1 &
    pids+=("$!")
    if ! wait_for_port "$port"; then
        echo "  FAILED   the server did not open its port $port (see $dir/server.log)"
        return 1
    fi
    for name in client_1 client_2; do
        container="pybiscus-smoke-$name-$$"
        CONTAINERS_TO_REMOVE+=("$container")
        "$engine" run --rm --name "$container" "${mounts[@]}" --network host \
            "$image" client launch "smoke-configs/$name.yml" \
            --server-address "localhost:$port" >"$dir/$name.log" 2>&1 &
        pids+=("$!")
    done

    if ! wait_for_exit "${pids[0]}" "$TIMEOUT"; then
        echo "  the run exceeded $TIMEOUT s: stopped"
        "$engine" stop "${CONTAINERS_TO_REMOVE[0]}" >/dev/null 2>&1
    fi
    for pid in "${pids[@]}"; do
        # a client outliving the server by more than a minute is stuck
        wait_for_exit "$pid" 60 || for container in "${CONTAINERS_TO_REMOVE[@]}"; do
            "$engine" stop "$container" >/dev/null 2>&1
        done
        wait "$pid"
        codes+=("$?")
    done
    judge_run "$dir" "${codes[@]}"
}

[ "$#" -eq 0 ] && set -- check run
status=0
for step in "$@"; do
    echo "== $step"
    case "$step" in
        check)         step_check ;;
        run)           step_run ;;
        build)         step_build ;;
        container-run) step_container_run ;;
        *)             echo "  unknown step: $step"; false ;;
    esac || { echo "== $step FAILED"; status=1; }
done
echo "work directory: $WORK"
exit "$status"
