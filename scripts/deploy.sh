#!/usr/bin/env bash
# Deploy ACEest to Kubernetes (Minikube) with a chosen release strategy.
#
# Usage: scripts/deploy.sh <strategy> <image_repo> <new_tag> [stable_tag]
#   strategy   rolling | blue-green | canary | canary-promote | shadow | ab-testing | all
#   image_repo e.g. docker.io/<dockerhub-user>/aceest-fitness
#   new_tag    version being released, e.g. 4.0.0
#   stable_tag last known good version, default 3.0.0
set -euo pipefail

STRATEGY=${1:?strategy required}
REPO=${2:?image repo required}
NEW_TAG=${3:?new tag required}
STABLE_TAG=${4:-3.0.0}
NS=aceest
TIMEOUT=180s
K8S_DIR="$(cd "$(dirname "$0")/../k8s" && pwd)"

render() {
  sed -e "s#IMAGE_REPO#${REPO}#g" -e "s#NEW_TAG#${NEW_TAG}#g" \
      -e "s#STABLE_TAG#${STABLE_TAG}#g" "$@"
}

wait_ready() {
  for d in "$@"; do
    kubectl -n "$NS" rollout status "deployment/$d" --timeout="$TIMEOUT"
  done
}

deploy_rolling() {
  if ! kubectl -n "$NS" get deployment/aceest-rolling >/dev/null 2>&1; then
    # First run: start from the stable version so the update has a revision to roll back to.
    render "$K8S_DIR"/rolling/*.yaml | sed "s#${REPO}:${NEW_TAG}#${REPO}:${STABLE_TAG}#" \
      | kubectl apply -f -
    kubectl -n "$NS" annotate deployment/aceest-rolling --overwrite \
      kubernetes.io/change-cause="release ${STABLE_TAG}"
    wait_ready aceest-rolling
  fi
  render "$K8S_DIR"/rolling/*.yaml | kubectl apply -f -
  kubectl -n "$NS" annotate deployment/aceest-rolling --overwrite \
    kubernetes.io/change-cause="release ${NEW_TAG}"
  if ! wait_ready aceest-rolling; then
    echo "Rolling update failed - rolling back"
    kubectl -n "$NS" rollout undo deployment/aceest-rolling
    wait_ready aceest-rolling
    exit 1
  fi
}

deploy_blue_green() {
  local live idle
  live=$(kubectl -n "$NS" get service aceest-bg -o jsonpath='{.spec.selector.color}' 2>/dev/null || true)
  if [ -z "$live" ]; then
    # First run: blue serves the stable version, green gets the new one.
    sed -e "s#COLOR_TAG#${STABLE_TAG}#g" -e "s#COLOR#blue#g" "$K8S_DIR/blue-green/deployment.yaml" \
      | render | kubectl apply -f -
    render "$K8S_DIR/blue-green/service.yaml" | kubectl apply -f -
    wait_ready aceest-bg-blue
    live=blue
  fi
  idle=$([ "$live" = "blue" ] && echo green || echo blue)

  sed -e "s#COLOR_TAG#${NEW_TAG}#g" -e "s#COLOR#${idle}#g" "$K8S_DIR/blue-green/deployment.yaml" \
    | render | kubectl apply -f -
  if ! wait_ready "aceest-bg-${idle}"; then
    echo "${idle} environment is not healthy - traffic stays on ${live}"
    exit 1
  fi
  kubectl -n "$NS" patch service aceest-bg -p \
    "{\"spec\":{\"selector\":{\"app\":\"aceest-bg\",\"color\":\"${idle}\"}}}"
  render "$K8S_DIR/blue-green/service-preview.yaml" \
    | sed "s#color: green#color: ${live}#" | kubectl apply -f -
  echo "Blue-green switch complete: live=${idle}, previous=${live} (kept for rollback)"
}

deploy_canary() {
  render "$K8S_DIR"/canary/*.yaml | kubectl apply -f -
  if ! wait_ready aceest-canary-stable aceest-canary-canary; then
    echo "Canary unhealthy - removing canary pods"
    kubectl -n "$NS" scale deployment/aceest-canary-canary --replicas=0
    exit 1
  fi
  echo "Canary live: 1 of 5 pods (~20% of traffic) run ${NEW_TAG}"
}

promote_canary() {
  kubectl -n "$NS" set image deployment/aceest-canary-stable aceest="${REPO}:${NEW_TAG}"
  wait_ready aceest-canary-stable
  kubectl -n "$NS" scale deployment/aceest-canary-canary --replicas=0
  echo "Canary promoted: all stable pods now run ${NEW_TAG}"
}

deploy_shadow() {
  render "$K8S_DIR"/shadow/*.yaml | kubectl apply -f -
  wait_ready aceest-shadow-production aceest-shadow-shadow
  echo "Shadow live: production=${STABLE_TAG}, mirrored traffic -> shadow=${NEW_TAG}"
}

deploy_ab() {
  render "$K8S_DIR"/ab-testing/*.yaml | kubectl apply -f -
  wait_ready aceest-ab-a aceest-ab-b
  echo "A/B live: A=${STABLE_TAG}, B=${NEW_TAG} (header X-Variant: B, or 50% weight)"
}

kubectl apply -f "$K8S_DIR/namespace.yaml"
case "$STRATEGY" in
  rolling) deploy_rolling ;;
  blue-green) deploy_blue_green ;;
  canary) deploy_canary ;;
  canary-promote) promote_canary ;;
  shadow) deploy_shadow ;;
  ab-testing) deploy_ab ;;
  all) deploy_rolling; deploy_blue_green; deploy_canary; deploy_shadow; deploy_ab ;;
  *) echo "Unknown strategy: $STRATEGY" >&2; exit 2 ;;
esac
kubectl -n "$NS" get deployments,services,ingress -o wide
