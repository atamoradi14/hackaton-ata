#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
expected_node_uid=87614cb1-f141-4c35-92de-9926d0757108
actual="$(kubectl get node ravand-k3s-01 -o jsonpath='{.metadata.uid}')"
[[ "$actual" == "$expected_node_uid" ]] || { echo 'Wrong cluster: node UID does not match the verified Helsinki node.'; exit 1; }
kubectl create namespace auckland-flowlab --dry-run=client -o yaml | kubectl apply -f -
if [[ -f provider.env ]]; then
  kubectl -n auckland-flowlab create secret generic auckland-flowlab-provider-keys --from-env-file=provider.env --dry-run=client -o yaml | kubectl apply -f -
else
  kubectl -n auckland-flowlab get secret auckland-flowlab-provider-keys >/dev/null
fi
if [[ -f caddy.env ]]; then
  kubectl -n auckland-flowlab create secret generic auckland-flowlab-caddy-settings --from-env-file=caddy.env --dry-run=client -o yaml | kubectl apply -f -
else
  kubectl -n auckland-flowlab get secret auckland-flowlab-caddy-settings >/dev/null
fi
kubectl -n auckland-flowlab create configmap auckland-flowlab-caddyfile --from-file=Caddyfile --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --dry-run=server -f resources.yaml
kubectl apply -f resources.yaml
kubectl -n auckland-flowlab rollout status deployment/auckland-flowlab-app --timeout=240s
kubectl -n auckland-flowlab rollout status deployment/auckland-flowlab-caddy --timeout=240s
kubectl -n auckland-flowlab get pods,services,pvc
# Credentials stay in the Kubernetes Secrets. Do not keep staging env copies.
rm -f provider.env caddy.env
