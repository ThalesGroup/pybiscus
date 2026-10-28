#!/usr/bin/bash

# Removes what run.sh created; the reports stay in the repository's experiments/.

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
kubectl delete namespace "${NAMESPACE:-pybiscus}" --ignore-not-found
