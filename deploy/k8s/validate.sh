#!/usr/bin/env bash
set -euo pipefail
[[ "$(kubectl get node ravand-k3s-01 -o jsonpath='{.metadata.uid}')" == 87614cb1-f141-4c35-92de-9926d0757108 ]] || exit 1
kubectl -n auckland-flowlab rollout status deployment/auckland-flowlab-app --timeout=240s
kubectl -n auckland-flowlab rollout status deployment/auckland-flowlab-caddy --timeout=240s
kubectl -n auckland-flowlab exec deployment/auckland-flowlab-app -- /usr/local/bin/_entrypoint.sh floodtwin doctor
kubectl -n auckland-flowlab exec deployment/auckland-flowlab-app -- /usr/local/bin/_entrypoint.sh floodtwin synthetic-quality run --root "/work/runs/quality-k8s-$(date -u +%Y%m%dT%H%M%SZ)"
[[ "$(curl --silent --output /dev/null --write-out '%{http_code}' https://daryajan.com/healthz)" == 200 ]]
curl --fail --show-error https://daryajan.com/healthz
echo; echo 'Cluster and actual hydraulic validation passed.'
