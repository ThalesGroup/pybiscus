#!/usr/bin/bash

# Smoke checks of a Pybiscus checkout, each step failing with a non-zero exit code:
#
#   launch/ci/smoke.sh [check] [run] [evaluation] [session] [presets] [new] [build] [container-run]     (default: check run)
#
#   check          every configuration of configs/ passes `server check` / `client check`, with the
#                  manifests of every plugin directory; docs/plugins-reference.md is up to date; the
#                  plugins' requirements (plugins deps) and conventions (plugins lint, bundled and
#                  hierarchical plugins); the linter still finds what its probes break
#                  (launch/ci/lint_probes_check.py);
#                  the configurations of every run of launch/campaign/ are valid (campaign --check)
#   run            a short federated run (mnist demo, server + 2 clients, CPU)
#   evaluation     the same run, then its exported model evaluated by the sites (configs/onnx_eval:
#                  onnxmodel, evaluateonly): the metrics of the trained session, a wrong hash refused
#                  (launch/ci/evaluation_check.py)
#   session        the same run in a session of the manager, without a browser: agents started with
#                  --register --accept-launch before their manager, the session launched through its
#                  API (launch/ci/session_check.py)
#   presets        the session's presets give the same configuration applied by an agent's form
#                  and by an agent launched by an order (launch/ci/presets_check.py, Playwright)
#   new            a plugin of each family created by `pybiscus plugins new`: its requirements, its
#                  conventions, its example configurations and a short run of each, as created
#   build          the two container images
#   container-run  the same short run, in containers of the pybiscus image
#
# Environment: PYBISCUS_PYTHON (default: "uv run --project <repo> python"), SMOKE_WORK (work
# directory, default: a new temporary one, kept for its logs), SMOKE_ROUNDS (2),
# SMOKE_MAX_SAMPLES (2000), SMOKE_THREADS (2), SMOKE_TIMEOUT (seconds per run, 900), SMOKE_GPU (set:
# container-run on the GPU PYBISCUS_GPU, bin/container_gpu).

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
    local logs="$WORK/check" config kind log failed=0 checked=0 manifests
    mkdir -p "$logs"
    # a shipped configuration may use the plugins of a directory a simple session does not load
    # (pybiscus-plugins-privacy-evaluation for the FedMIA demo)
    manifests="${PYBISCUS_PLUGIN_CONF_PATH:-$(cd "$REPO" && ls pybiscus-plugins*/plugins-conf.yml | paste -sd:)}"
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
        if (cd "$REPO" && PYBISCUS_PLUGIN_CONF_PATH="$manifests" $PYTHON pybiscus/main.py "$kind" check "$config") >"$log" 2>&1; then
            echo "  ok       $config"
        else
            echo "  FAILED   $config ($kind check, see $log)"
            failed=$((failed + 1))
        fi
    done < <(cd "$REPO" && find configs -name '*.yml' -not -path 'configs/uploaded/*' | sort)
    echo "  $checked configuration(s) checked, $failed failed"
    # generated from the bundled and the hierarchical plugins: a plugin changed without it is caught here
    log="$logs/plugins-reference.log"
    if (cd "$REPO" && PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml \
            $PYTHON pybiscus/main.py plugins doc --check) >"$log" 2>&1; then
        echo "  ok       docs/plugins-reference.md"
    else
        echo "  FAILED   docs/plugins-reference.md is not up to date (pybiscus plugins doc, see $log)"
        failed=$((failed + 1))
    fi
    # what the plugins import against their requirements.txt, for every plugin directory; installed
    # only for those a simple session loads: the privacy evaluation's are an extra
    log="$logs/plugins-deps.log"
    # the test-only plugins (campaigns, presets) too: their manifests are in launch/
    if (cd "$REPO" && PYBISCUS_PLUGIN_CONF_PATH="$manifests:launch/campaign/test-plugins-conf.yml:launch/ci/test-plugins-conf.yml" \
            $PYTHON pybiscus/main.py plugins deps --declarations >"$log" 2>&1 \
            && PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml \
               $PYTHON pybiscus/main.py plugins deps >>"$log" 2>&1); then
        echo "  ok       the plugins' requirements.txt (pybiscus plugins deps)"
    else
        echo "  FAILED   the plugins' requirements.txt (pybiscus plugins deps, see $log)"
        failed=$((failed + 1))
    fi
    # the privacy evaluation's plugins are not finalized: left out until they are
    log="$logs/plugins-lint.log"
    if (cd "$REPO" && PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:pybiscus-plugins-hierarchical/plugins-conf.yml \
            $PYTHON pybiscus/main.py plugins lint) >"$log" 2>&1; then
        echo "  ok       the plugins' conventions (pybiscus plugins lint)"
    else
        echo "  FAILED   the plugins' conventions (pybiscus plugins lint, see $log)"
        failed=$((failed + 1))
    fi
    # the linter's own regression: each rule still fires on its probe, and only there
    log="$logs/lint-probes.log"
    if (cd "$REPO" && $PYTHON launch/ci/lint_probes_check.py) >"$log" 2>&1; then
        echo "  ok       the linter's probes (launch/ci/lint_probes_check.py)"
    else
        echo "  FAILED   the linter's probes (launch/ci/lint_probes_check.py, see $log)"
        failed=$((failed + 1))
    fi
    # the campaigns with the manifests their runs load (the default one and their plugin_manifests),
    # not the configs' list above: a test-only plugin they need is declared there only
    while IFS= read -r config; do
        log="$logs/$(echo "$config" | tr '/' '_').log"
        if (cd "$REPO" && $PYTHON launch/campaign/strategy_campaign.py --check "$config") >"$log" 2>&1; then
            echo "  ok       $config ($(tail -1 "$log" | sed 's/^ *//'))"
        else
            echo "  FAILED   $config (campaign --check, see $log)"
            failed=$((failed + 1))
        fi
    done < <(cd "$REPO" && grep -l '^variants:' launch/campaign/*.yml | sort)
    [ "$failed" -eq 0 ]
}

# the experiments and logs of a run go to its own directory, never to the repository's
prepare_run_dir() {
    local dir="$1" demo="${2:-$DEMO}"
    mkdir -p "$dir/configs" "$dir/experiments" "$REPO/datasets"
    ln -sfn "$REPO/pybiscus-plugins" "$dir/pybiscus-plugins"
    ln -sfn "$REPO/datasets" "$dir/datasets"
    $PYTHON "$REPO/launch/ci/smoke_configs.py" "$REPO/$demo" "$dir/configs" "$MAX_SAMPLES" "$THREADS"
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
    # an evaluation session writes its report, no checkpoint
    if [ -z "$(find "$dir/experiments" -name "${EXPECTED_REPORT:-final_checkpoint.pt}")" ]; then
        echo "  FAILED   no ${EXPECTED_REPORT:-final_checkpoint.pt} under $dir/experiments"
        failed=1
    fi
    [ "$failed" -eq 0 ] && echo "  ok       $ROUNDS rounds, server and 2 clients, logs in $dir"
    return "$failed"
}

# a server and two clients from the configurations of $1/{server,client_1,client_2}.yml, in the
# current directory (their root_dir), judged as the demo's run
run_three() {
    local configs="$1" port pids=() codes=() pid name
    port="$(free_port)" || return 1
    setsid $PYTHON "$REPO/pybiscus/main.py" server launch "$configs/server.yml" \
        --num-rounds "$ROUNDS" --server-listen-address "[::]:$port" >server.log 2>&1 &
    pids+=("$!"); GROUPS_TO_KILL+=("$!")
    if ! wait_for_port "$port"; then
        echo "  FAILED   the server did not open its port $port (see $PWD/server.log)"
        return 1
    fi
    for name in client_1 client_2; do
        setsid $PYTHON "$REPO/pybiscus/main.py" client launch "$configs/$name.yml" \
            --server-address "localhost:$port" >"$name.log" 2>&1 &
        pids+=("$!"); GROUPS_TO_KILL+=("$!")
    done
    if ! wait_for_exit "${pids[0]}" "$TIMEOUT"; then
        echo "  the run exceeded $TIMEOUT s: stopped"
        kill -- "-${pids[0]}" 2>/dev/null
    fi
    for pid in "${pids[@]}"; do
        wait_for_exit "$pid" 60 || kill -- "-$pid" 2>/dev/null
        wait "$pid"
        codes+=("$?")
    done
    judge_run "$PWD" "${codes[@]}"
}

# the plugins `pybiscus plugins new` creates, one of each family, as they are: their requirements,
# their example configurations, a run of each (synthetic data): the templates do not drift
step_new() {
    local dir="$WORK/new" plugins kind name failed=0 log config
    plugins="$dir/myplugins"
    mkdir -p "$dir"
    for kind in model data strategydecorator; do
        name="my$kind"
        if ! (cd "$REPO" && $PYTHON pybiscus/main.py plugins new "$kind" "$name" --dir "$plugins") >"$dir/new-$kind.log" 2>&1; then
            echo "  FAILED   plugins new $kind (see $dir/new-$kind.log)"
            failed=1
        fi
    done
    [ "$failed" -eq 0 ] || return 1
    # only now: every command reads the manifests at its start, and this one did not exist
    export PYBISCUS_PLUGIN_CONF_PATH="$REPO/pybiscus-plugins/plugins-conf.yml:$plugins/plugins-conf.yml"
    if ! (cd "$REPO" && $PYTHON pybiscus/main.py plugins deps) >"$dir/deps.log" 2>&1; then
        echo "  FAILED   their requirements (pybiscus plugins deps, see $dir/deps.log)"
        return 1
    fi
    if ! (cd "$REPO" && PYBISCUS_PLUGIN_CONF_PATH="$plugins/plugins-conf.yml" $PYTHON pybiscus/main.py plugins lint) >"$dir/lint.log" 2>&1; then
        echo "  FAILED   their conventions (pybiscus plugins lint, see $dir/lint.log)"
        return 1
    fi
    for kind in model data strategydecorator; do
        name="my$kind"
        for config in server client_1 client_2; do
            log="$dir/check-$name-$config.log"
            if ! (cd "$REPO" && $PYTHON pybiscus/main.py "$([ "$config" = server ] && echo server || echo client)" check \
                    "$plugins/$kind/$name/examples/$config.yml") >"$log" 2>&1; then
                echo "  FAILED   $kind/$name/examples/$config.yml (check, see $log)"
                failed=1
            fi
        done
    done
    [ "$failed" -eq 0 ] || return 1
    echo "  ok       a plugin of each family created, its requirements, conventions and 3 examples valid"
    for kind in model data strategydecorator; do
        name="my$kind"
        mkdir -p "$dir/run-$name/experiments"
        # not in a subshell: the processes it starts must reach the cleanup's GROUPS_TO_KILL
        cd "$dir/run-$name" || return 1
        run_three "$plugins/$kind/$name/examples" || failed=1
    done
    cd "$REPO" || return 1
    unset PYBISCUS_PLUGIN_CONF_PATH
    [ "$failed" -eq 0 ]
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

step_evaluation() {
    local dir="$WORK/evaluation" trained evaluated model status=0
    prepare_run_dir "$dir/train" || return 1
    # not in a subshell: the processes it starts must reach the cleanup's GROUPS_TO_KILL
    cd "$dir/train" || return 1
    run_three configs || { cd "$REPO"; return 1; }
    trained="$(realpath "$dir/train/experiments/current")"
    prepare_run_dir "$dir/eval" configs/onnx_eval || return 1
    model="$dir/eval/experiments/published/mnist_cnn.onnx"
    mkdir -p "$(dirname "$model")" && cp "$trained/model.onnx" "$model" || return 1
    export PYBISCUS_ONNX_MODEL="$model"
    PYBISCUS_ONNX_SHA256="$(sha256sum "$model" | cut -d' ' -f1)"
    export PYBISCUS_ONNX_SHA256
    cd "$dir/eval" || return 1
    EXPECTED_REPORT=evaluation.json run_three configs || status=1
    # the same model on each site's test section, at scheduled rounds (evaluation_section_check.py)
    prepare_run_dir "$dir/eval-test" configs/onnx_eval || return 1
    $PYTHON "$REPO/launch/ci/evaluation_section_check.py" --prepare "$dir/eval-test/configs" || return 1
    cd "$dir/eval-test" || return 1
    [ "$status" -eq 0 ] && { EXPECTED_REPORT=evaluation.json run_three configs || status=1; }
    cd "$REPO" || return 1
    unset PYBISCUS_ONNX_MODEL PYBISCUS_ONNX_SHA256
    [ "$status" -eq 0 ] || return 1
    evaluated="$(realpath "$dir/eval/experiments/current")"
    $PYTHON "$REPO/launch/ci/evaluation_check.py" "$trained" "$evaluated" "$dir/eval" $PYTHON "$REPO/pybiscus/main.py" || status=1
    $PYTHON "$REPO/launch/ci/evaluation_section_check.py" "$dir/eval-test" || status=1
    return "$status"
}

step_session() {
    local dir="$WORK/session"
    prepare_run_dir "$dir" || return 1
    $PYTHON "$REPO/launch/ci/session_check.py" "$dir" "$dir/configs" "$ROUNDS" "$TIMEOUT"
}

step_presets() {
    uv run --quiet "$REPO/launch/ci/presets_check.py"
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
    # SMOKE_GPU=1: the containers get the GPU of PYBISCUS_GPU (bin/container_gpu); on CPU otherwise
    [ -n "$SMOKE_GPU" ] && mounts+=($(container_gpu))

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
        evaluation)    step_evaluation ;;
        session)       step_session ;;
        presets)       step_presets ;;
        new)           step_new ;;
        build)         step_build ;;
        container-run) step_container_run ;;
        *)             echo "  unknown step: $step"; false ;;
    esac || { echo "== $step FAILED"; status=1; }
done
echo "work directory: $WORK"
exit "$status"
