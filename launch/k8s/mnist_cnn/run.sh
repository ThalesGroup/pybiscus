#!/usr/bin/bash

# The mnist demo of launch/uv/mnist_cnn/distributed/ in a Kubernetes cluster (tested on k3s, one
# node): the Flower server and two clients as Jobs, the reports in the repository's experiments/.
# Environment: NAMESPACE (pybiscus), NUM_ROUNDS (10), K8S_IMAGE (the pybiscus image of this version,
# imported into the cluster beforehand), KUBECONFIG (~/.kube/config).

set -e

HERE="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

# k3s's kubectl reads /etc/rancher/k3s/k3s.yaml otherwise, readable by root only
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
NAMESPACE="${NAMESPACE:-pybiscus}"
NUM_ROUNDS="${NUM_ROUNDS:-10}"
# an image saved by podman keeps its localhost/ prefix once imported into containerd
IMAGE="${K8S_IMAGE:-localhost/$("$REPO/bin/pybiscus_image")}"

substitute() {
    sed -e "s|@REPO@|$REPO|g" -e "s|@IMAGE@|$IMAGE|g" -e "s|@NUM_ROUNDS@|$NUM_ROUNDS|g" \
        -e "s|@UID@|$(id -u)|g" -e "s|@GID@|$(id -g)|g" "$@"
}

echo "[k8s] image $IMAGE, namespace $NAMESPACE, $NUM_ROUNDS rounds"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
# a Job cannot be updated: the previous run's are removed
kubectl -n "$NAMESPACE" delete job -l app.kubernetes.io/part-of=pybiscus-mnist --ignore-not-found --wait
kubectl -n "$NAMESPACE" create configmap pybiscus-mnist-configs \
    --from-file="$REPO/configs/mnist_cnn/distributed" --dry-run=client -o yaml | kubectl apply -f -

mkdir -p "$REPO/experiments"
substitute "$HERE/server.yaml" | kubectl -n "$NAMESPACE" apply -f -
for client in client_1 client_2; do
    # a Kubernetes name has no underscore
    substitute -e "s|@CLIENT@|$client|g" -e "s|@CLIENT_DNS@|${client//_/-}|g" "$HERE/client.yaml" \
        | kubectl -n "$NAMESPACE" apply -f -
done

echo "[k8s] follow:  kubectl -n $NAMESPACE logs -f job/flower-server"
echo "[k8s] state:   kubectl -n $NAMESPACE get jobs,pods"
echo "[k8s] remove:  $HERE/stop.sh"
